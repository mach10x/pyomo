#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright 2017 National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

import os
import platform
import shutil
import stat
import sys
import tempfile

import pyutilib.th as unittest
from pyutilib.subprocess import run

import pyomo.common.config as config
from pyomo.common.fileutils import (
    thisFile, find_file, find_library, find_executable,
    _system, _path, _libExt,
)

_thisFile = thisFile()

class TestFileUtils(unittest.TestCase):
    def setUp(self):
        self.tmpdir = None
        self.basedir = os.path.abspath(os.path.curdir)
        self.config = config.PYOMO_CONFIG_DIR
        self.ld_library_path = os.environ.get('LD_LIBRARY_PATH', None)
        self.path = os.environ.get('PATH', None)

    def tearDown(self):
        if self.tmpdir:
            shutil.rmtree(self.tmpdir)
            os.chdir(self.basedir)
        if self.ld_library_path is None:
            os.environ.pop('LD_LIBRARY_PATH', None)
        else:
            os.environ['LD_LIBRARY_PATH'] = self.ld_library_path
        if self.path is None:
            os.environ.pop('PATH', None)
        else:
            os.environ['PATH'] = self.path
        config.PYOMO_CONFIG_DIR = self.config

    def test_thisFile(self):
        self.assertEquals(_thisFile, __file__.replace('.pyc','.py'))
        self.assertEquals(run([
            sys.executable,'-c',
            'from pyomo.common.fileutils import thisFile;print(thisFile())'
        ])[1].strip(), '<string>')
        self.assertEquals(run(
            [sys.executable],
            stdin='from pyomo.common.fileutils import thisFile;'
            'print(thisFile())'
        )[1].strip(), '<stdin>')

    def test_system(self):
        self.assertTrue(platform.system().lower().startswith(_system()))
        self.assertNotIn('.', _system())
        self.assertNotIn('-', _system())
        self.assertNotIn('_', _system())

    def test_path(self):
        orig_path = os.environ.get('PATH', None)
        if orig_path:
            self.assertEqual(os.pathsep.join(_path()), os.environ['PATH'])
        os.environ.pop('PATH', None)
        self.assertEqual(os.pathsep.join(_path()), os.defpath)
        # PATH restored by teadDown()

    def test_findfile(self):
        self.tmpdir = os.path.abspath(tempfile.mkdtemp())
        subdir_name = 'aaa'
        subdir = os.path.join(self.tmpdir, subdir_name)
        os.mkdir(subdir)
        os.chdir(self.tmpdir)

        fname = 'foo.py'
        self.assertEqual(
            None,
            find_file(fname)
        )

        open(os.path.join(self.tmpdir,fname),'w').close()
        open(os.path.join(subdir,fname),'w').close()
        open(os.path.join(subdir,'aaa'),'w').close()
        # we can find files in the CWD
        self.assertEqual(
            os.path.join(self.tmpdir,fname),
            find_file(fname)
        )
        # unless we don't look in the cwd
        self.assertEqual(
            None,
            find_file(fname, cwd=False)
        )
        # cwd overrides pathlist
        self.assertEqual(
            os.path.join(self.tmpdir,fname),
            find_file(fname, pathlist=[subdir])
        )
        self.assertEqual(
            os.path.join(subdir,fname),
            find_file(fname, pathlist=[subdir], cwd=False)
        )
        # ...unless the CWD match fails the MODE check
        self.assertEqual(
            ( os.path.join(self.tmpdir,fname)
              if _system() in ('windiws','cygwin')
              else None ),
            find_file(fname, pathlist=[subdir], mode=os.X_OK)
        )
        mode = os.stat(os.path.join(subdir,fname)).st_mode
        os.chmod( os.path.join(subdir,fname),
                  mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH )
        self.assertEqual(
            os.path.join(subdir,fname),
            find_file(fname, pathlist=[subdir], mode=os.X_OK)
        )

        # implicit extensions work (even if they are not necessary)
        self.assertEqual(
            os.path.join(self.tmpdir,fname),
            find_file(fname, ext='.py')
        )
        self.assertEqual(
            os.path.join(self.tmpdir,fname),
            find_file(fname, ext=['.py'])
        )

        # implicit extensions work (and when they are not necessary)
        self.assertEqual(
            os.path.join(self.tmpdir,fname),
            find_file(fname[:-3], ext='.py')
        )
        self.assertEqual(
            os.path.join(self.tmpdir,fname),
            find_file(fname[:-3], ext=['.py'])
        )

        # only files are found
        self.assertEqual(
            os.path.join(subdir,subdir_name),
            find_file( subdir_name,
                       pathlist=[self.tmpdir, subdir], cwd=False )
        )

        # empty dirs are skipped
        self.assertEqual(
            os.path.join(subdir,subdir_name),
            find_file( subdir_name,
                       pathlist=['', self.tmpdir, subdir], cwd=False )
        )

    def test_find_library(self):
        self.tmpdir = os.path.abspath(tempfile.mkdtemp())
        os.chdir(self.tmpdir)

        config.PYOMO_CONFIG_DIR = self.tmpdir
        config_libdir = os.path.join(self.tmpdir, 'lib')
        os.mkdir(config_libdir)
        config_bindir = os.path.join(self.tmpdir, 'bin')
        os.mkdir(config_bindir)

        ldlibdir_name = 'in_ld_lib'
        ldlibdir = os.path.join(self.tmpdir, ldlibdir_name)
        os.mkdir(ldlibdir)
        os.environ['LD_LIBRARY_PATH'] = os.pathsep + ldlibdir + os.pathsep

        pathdir_name = 'in_path'
        pathdir = os.path.join(self.tmpdir, pathdir_name)
        os.mkdir(pathdir)
        os.environ['PATH'] = os.pathsep + pathdir + os.pathsep

        libExt = _libExt[_system()][0]

        f_in_cwd_ldlib_path = 'f_in_cwd_ldlib_path'
        open(os.path.join(self.tmpdir,f_in_cwd_ldlib_path),'w').close()
        open(os.path.join(ldlibdir,f_in_cwd_ldlib_path),'w').close()
        open(os.path.join(pathdir,f_in_cwd_ldlib_path),'w').close()
        f_in_ldlib_extension = 'f_in_ldlib_extension'
        open(os.path.join(ldlibdir,f_in_ldlib_extension + libExt),'w').close()
        f_in_path = 'f_in_path'
        open(os.path.join(pathdir,f_in_path),'w').close()

        f_in_configlib = 'f_in_configlib'
        open(os.path.join(config_libdir, f_in_configlib),'w').close()
        f_in_configbin = 'f_in_configbin'
        open(os.path.join(config_bindir, f_in_ldlib_extension),'w').close()
        open(os.path.join(config_bindir, f_in_configbin),'w').close()


        self.assertEqual(
            os.path.join(self.tmpdir, f_in_cwd_ldlib_path),
            find_library(f_in_cwd_ldlib_path)
        )
        self.assertEqual(
            os.path.join(ldlibdir, f_in_cwd_ldlib_path),
            find_library(f_in_cwd_ldlib_path, cwd=False)
        )
        self.assertEqual(
            os.path.join(ldlibdir, f_in_ldlib_extension) + libExt,
            find_library(f_in_ldlib_extension)
        )
        self.assertEqual(
            os.path.join(pathdir, f_in_path),
            find_library(f_in_path)
        )
        self.assertEqual(
            None,
            find_library(f_in_path, include_PATH=False)
        )
        self.assertEqual(
            os.path.join(pathdir, f_in_path),
            find_library(f_in_path, pathlist=os.pathsep+pathdir+os.pathsep)
        )
        # test an explicit pathlist overrides LD_LIBRARY_PATH
        self.assertEqual(
            os.path.join(pathdir, f_in_cwd_ldlib_path),
            find_library(f_in_cwd_ldlib_path, cwd=False, pathlist=[pathdir])
        )
        # test that the PYOMO_CONFIG_DIR is included
        self.assertEqual(
            os.path.join(config_libdir, f_in_configlib),
            find_library(f_in_configlib)
        )
        # and the Bin dir
        self.assertEqual(
            os.path.join(config_bindir, f_in_configbin),
            find_library(f_in_configbin)
        )
        # ... but only if include_PATH is true
        self.assertEqual(
            None,
            find_library(f_in_configbin, include_PATH=False)
        )
        # And none of them if the pathlist is specified
        self.assertEqual(
            None,
            find_library(f_in_configlib, pathlist=pathdir)
        )
        self.assertEqual(
            None,
            find_library(f_in_configbin, pathlist=pathdir)
        )

