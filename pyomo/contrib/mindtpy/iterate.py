"""Iteration loop for MindtPy."""
from __future__ import division

from pyomo.contrib.mindtpy.cut_generation import (add_oa_cuts, add_ecp_cuts,
                                                  add_int_cut)

from pyomo.contrib.mindtpy.mip_solve import (solve_OA_master,
                                             handle_master_mip_optimal, handle_master_mip_other_conditions)
from pyomo.contrib.mindtpy.nlp_solve import (solve_NLP_subproblem,
                                             handle_NLP_subproblem_optimal, handle_NLP_subproblem_infeasible,
                                             handle_NLP_subproblem_other_termination)
from pyomo.core import minimize, Objective
from pyomo.opt import TerminationCondition as tc
from pyomo.contrib.gdpopt.util import get_main_elapsed_time


def MindtPy_iteration_loop(solve_data, config):
    working_model = solve_data.working_model
    main_objective = next(
        working_model.component_data_objects(Objective, active=True))
    while solve_data.mip_iter < config.iteration_limit:

        config.logger.info(
            '---MindtPy Master Iteration %s---'
            % solve_data.mip_iter)

        if algorithm_should_terminate(solve_data, config):
            break

        solve_data.mip_subiter = 0
        # solve MILP master problem
        if config.strategy == 'OA' or config.strategy == 'ECP':
            master_mip, master_mip_results = solve_OA_master(
                solve_data, config)
            if master_mip_results.solver.termination_condition is tc.optimal:
                handle_master_mip_optimal(master_mip, solve_data, config)
            else:
                handle_master_mip_other_conditions(master_mip, master_mip_results,
                                                   solve_data, config)
            # Call the MILP post-solve callback
            config.call_after_master_solve(master_mip, solve_data)
        else:
            raise NotImplementedError()

        if algorithm_should_terminate(solve_data, config):
            break

        if config.single_tree is False and config.strategy != 'ECP':  # if we don't use lazy callback, i.e. LP_NLP
            # Solve NLP subproblem
            # The constraint linearization happens in the handlers
            fixed_nlp, fixed_nlp_result = solve_NLP_subproblem(
                solve_data, config)
            if fixed_nlp_result.solver.termination_condition is tc.optimal:
                handle_NLP_subproblem_optimal(fixed_nlp, solve_data, config)
            elif fixed_nlp_result.solver.termination_condition is tc.infeasible:
                handle_NLP_subproblem_infeasible(fixed_nlp, solve_data, config)
            else:
                handle_NLP_subproblem_other_termination(fixed_nlp, fixed_nlp_result.solver.termination_condition,
                                                        solve_data, config)
            # Call the NLP post-solve callback
            config.call_after_subproblem_solve(fixed_nlp, solve_data)

        if config.strategy == 'ECP':
            add_ecp_cuts(solve_data.mip, solve_data, config)

        # if config.strategy == 'PSC':
        #     # If the hybrid algorithm is not making progress, switch to OA.
        #     progress_required = 1E-6
        #     if main_objective.sense == minimize:
        #         log = solve_data.LB_progress
        #         sign_adjust = 1
        #     else:
        #         log = solve_data.UB_progress
        #         sign_adjust = -1
        #     # Maximum number of iterations in which the lower (optimistic)
        #     # bound does not improve before switching to OA
        #     max_nonimprove_iter = 5
        #     making_progress = True
        #     # TODO-romeo Unneccesary for OA and LOA, right?
        #     for i in range(1, max_nonimprove_iter + 1):
        #         try:
        #             if (sign_adjust * log[-i]
        #                     <= (log[-i - 1] + progress_required)
        #                     * sign_adjust):
        #                 making_progress = False
        #             else:
        #                 making_progress = True
        #                 break
        #         except IndexError:
        #             # Not enough history yet, keep going.
        #             making_progress = True
        #             break
        #     if not making_progress and (
        #             config.strategy == 'hPSC' or
        #             config.strategy == 'PSC'):
        #         config.logger.info(
        #             'Not making enough progress for {} iterations. '
        #             'Switching to OA.'.format(max_nonimprove_iter))
        #         config.strategy = 'OA'


def algorithm_should_terminate(solve_data, config):
    """Check if the algorithm should terminate.

    Termination conditions based on solver options and progress.
    Sets the solve_data.results.solver.termination_condition to the appropriate
    condition, i.e. optimal, maxIterations, maxTimeLimit

    """

    # Check bound convergence
    if solve_data.LB + config.bound_tolerance >= solve_data.UB:
        config.logger.info(
            'MindtPy exiting on bound convergence. '
            'LB: {} + (tol {}) >= UB: {}\n'.format(
                solve_data.LB, config.bound_tolerance, solve_data.UB))
        solve_data.results.solver.termination_condition = tc.optimal
        return True

    # Check iteration limit
    if solve_data.mip_iter >= config.iteration_limit:
        config.logger.info(
            'MindtPy unable to converge bounds '
            'after {} master iterations.'.format(solve_data.mip_iter))
        config.logger.info(
            'Final bound values: LB: {}  UB: {}'.
            format(solve_data.LB, solve_data.UB))
        solve_data.results.solver.termination_condition = tc.maxIterations
        return True

    # Check time limit
    if get_main_elapsed_time(solve_data.timing) >= config.time_limit:
        config.logger.info(
            'MindtPy unable to converge bounds '
            'before time limit of {} seconds. '
            'Elapsed: {} seconds'
            .format(config.time_limit, get_main_elapsed_time(solve_data.timing)))
        config.logger.info(
            'Final bound values: LB: {}  UB: {}'.
            format(solve_data.LB, solve_data.UB))
        solve_data.results.solver.termination_condition = tc.maxTimeLimit
        return True

    if config.strategy == 'ECP':
        MindtPy = solve_data.working_model.MindtPy_utils
        nonlinear_constraints = [c for c in MindtPy.constraint_list if
                                 c.body.polynomial_degree() not in (1, 0)]
        for nlc in nonlinear_constraints:
            if nlc.has_lb():
                if nlc.lslack() < -config.ECP_tolerance:
                    return False
            if nlc.has_ub():
                if nlc.uslack() < -config.ECP_tolerance:
                    return False
        config.logger.info(
            'MindtPy exiting on nonlinear constraints satisfaction. '
            'LB: {}\n'.format(
                solve_data.LB))
        solve_data.best_solution_found = solve_data.working_model.clone()
        solve_data.results.solver.termination_condition = tc.optimal
        return True
    # if not algorithm_is_making_progress(solve_data, config):
    #     config.logger.debug(
    #         'Algorithm is not making enough progress. '
    #         'Exiting iteration loop.')
    #     return True
    return False
