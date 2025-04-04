#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008-2025
#  National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

# -*- coding: utf-8 -*-
"""Tests for global LP/NLP in the MindtPy solver."""
import pyomo.common.unittest as unittest
from pyomo.contrib.mindtpy.tests.eight_process_problem import EightProcessFlowsheet
from pyomo.contrib.mindtpy.tests.nonconvex1 import Nonconvex1
from pyomo.contrib.mindtpy.tests.nonconvex2 import Nonconvex2
from pyomo.contrib.mindtpy.tests.nonconvex3 import Nonconvex3
from pyomo.contrib.mindtpy.tests.nonconvex4 import Nonconvex4
from pyomo.environ import SolverFactory, value
from pyomo.opt import TerminationCondition
from pyomo.contrib.mcpp import pyomo_mcpp

required_solvers = ('baron', 'cplex_persistent')
if not all(SolverFactory(s).available(exception_flag=False) for s in required_solvers):
    subsolvers_available = False
elif not SolverFactory('baron').license_is_valid():
    subsolvers_available = False
else:
    subsolvers_available = True


model_list = [
    EightProcessFlowsheet(convex=False),
    Nonconvex1(),
    Nonconvex2(),
    Nonconvex3(),
    Nonconvex4(),
]


@unittest.skipIf(
    not subsolvers_available,
    'Required subsolvers %s are not available' % (required_solvers,),
)
@unittest.skipIf(not pyomo_mcpp.mcpp_available(), 'MC++ is not available')
class TestMindtPy(unittest.TestCase):
    """Tests for the MindtPy solver plugin."""

    def check_optimal_solution(self, model, places=1):
        for var in model.optimal_solution:
            self.assertAlmostEqual(
                var.value, model.optimal_solution[var], places=places
            )

    def test_GOA(self):
        """Test the global outer approximation decomposition algorithm."""
        with SolverFactory('mindtpy') as opt:
            for model in model_list:
                model = model.clone()
                results = opt.solve(
                    model,
                    strategy='GOA',
                    mip_solver=required_solvers[1],
                    nlp_solver=required_solvers[0],
                    single_tree=True,
                )

                self.assertIn(
                    results.solver.termination_condition,
                    [TerminationCondition.optimal, TerminationCondition.feasible],
                )
                self.assertAlmostEqual(
                    value(model.objective.expr), model.optimal_value, places=2
                )
                self.check_optimal_solution(model)

    def test_GOA_tabu_list(self):
        """Test the global outer approximation decomposition algorithm."""
        with SolverFactory('mindtpy') as opt:
            for model in model_list:
                model = model.clone()
                results = opt.solve(
                    model,
                    strategy='GOA',
                    mip_solver=required_solvers[1],
                    nlp_solver=required_solvers[0],
                    single_tree=True,
                    use_tabu_list=True,
                )

                self.assertIn(
                    results.solver.termination_condition,
                    [TerminationCondition.optimal, TerminationCondition.feasible],
                )
                self.assertAlmostEqual(
                    value(model.objective.expr), model.optimal_value, places=2
                )
                self.check_optimal_solution(model)

    @unittest.skipUnless(
        SolverFactory('gurobi_persistent').available(exception_flag=False)
        and SolverFactory('gurobi_direct').available(),
        'gurobi_persistent and gurobi_direct solver is not available',
    )
    def test_GOA_Gurobi(self):
        """Test the global outer approximation decomposition algorithm."""
        with SolverFactory('mindtpy') as opt:
            for model in model_list:
                model = model.clone()
                results = opt.solve(
                    model,
                    strategy='GOA',
                    mip_solver='gurobi_persistent',
                    nlp_solver=required_solvers[0],
                    single_tree=True,
                )

                self.assertIn(
                    results.solver.termination_condition,
                    [TerminationCondition.optimal, TerminationCondition.feasible],
                )
                self.assertAlmostEqual(
                    value(model.objective.expr), model.optimal_value, places=2
                )
                self.check_optimal_solution(model)


if __name__ == '__main__':
    unittest.main()
