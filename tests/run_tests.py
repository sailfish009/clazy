#!/usr/bin/env python2

import sys, os, subprocess, string, re, json, threading, multiprocessing
from threading import Thread
from sys import platform as _platform

def isWindows():
    return _platform == 'win32'

class QtInstallation:
    def __init__(self):
        self.int_version = 000
        self.qmake_header_path = "/usr/include/qt/"

    def compiler_flags(self):
        return "-isystem " + self.qmake_header_path + ("" if isWindows() else " -fPIC")

class Test:
    def __init__(self, check):
        self.filename = ""
        self.minimum_qt_version = 500
        self.maximum_qt_version = 999
        self.minimum_clang_version = 370
        self.compare_everything = False
        self.isFixedFile = False
        self.link = False # If true we also call the linker
        self.check = check
        self.expects_failure = False
        self.qt_major_version = 5 # Tests use Qt 5 by default
        self.env = os.environ
        self.checks = []
        self.flags = ""
        self.must_fail = False
        self.blacklist_platforms = []

    def isScript(self):
        return self.filename.endswith(".sh")

    def setQtMajorVersion(self, major_version):
        if major_version == 4:
            self.qt_major_version = 4
            if self.minimum_qt_version >= 500:
                self.minimum_qt_version = 400

    def envString(self):
        result = ""
        for key in self.env:
            result += key + '="' + self.env[key] + '" '
        return result

    def setEnv(self, e):
        self.env = os.environ.copy()
        for key in e:
            key_str = key.encode('ascii', 'ignore')
            self.env[key_str] = e[key].encode('ascii', 'ignore')

class Check:
    def __init__(self, name):
        self.name = name
        self.minimum_clang_version = 370 # clang 3.7.0
        self.minimum_qt_version = 500
        self.maximum_qt_version = 999
        self.enabled = True
        self.tests = []
#-------------------------------------------------------------------------------
# utility functions #1

def get_command_output(cmd, test_env = os.environ):
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, env=test_env)
    except subprocess.CalledProcessError, e:
        return e.output,False

    return output,True

def load_json(check_name):
    check = Check(check_name)
    filename = check_name + "/config.json"
    if not os.path.exists(filename):
        print "Error: " + filename + " not found"
        return check

    f = open(filename, 'r')
    contents = f.read()
    f.close()
    decoded = json.loads(contents)
    check_blacklist_platforms = []

    if 'minimum_clang_version' in decoded:
        check.minimum_clang_version = decoded['minimum_clang_version']

    if 'minimum_qt_version' in decoded:
        check.minimum_qt_version = decoded['minimum_qt_version']

    if 'maximum_qt_version' in decoded:
        check.maximum_qt_version = decoded['maximum_qt_version']

    if 'enabled' in decoded:
        check.enabled = decoded['enabled']

    if 'blacklist_platforms' in decoded:
        check_blacklist_platforms = decoded['blacklist_platforms']

    if 'tests' in decoded:
        for t in decoded['tests']:
            test = Test(check)
            test.blacklist_platforms = check_blacklist_platforms
            test.filename = t['filename']

            if 'minimum_qt_version' in t:
                test.minimum_qt_version = t['minimum_qt_version']
            else:
                test.minimum_qt_version = check.minimum_qt_version

            if 'maximum_qt_version' in t:
                test.maximum_qt_version = t['maximum_qt_version']
            else:
                test.maximum_qt_version = check.maximum_qt_version

            if 'minimum_clang_version' in t:
                test.minimum_clang_version = t['minimum_clang_version']
            else:
                test.minimum_clang_version = check.minimum_clang_version

            if 'blacklist_platforms' in t:
                test.blacklist_platforms = t['blacklist_platforms']
            if 'compare_everything' in t:
                test.compare_everything = t['compare_everything']
            if 'isFixedFile' in t:
                test.isFixedFile = t['isFixedFile']
            if 'link' in t:
                test.link = t['link']
            if 'qt_major_version' in t:
                test.setQtMajorVersion(t['qt_major_version'])
            if 'env' in t:
                test.setEnv(t['env'])
            if 'checks' in t:
                test.checks = t['checks']
            if 'flags' in t:
                test.flags = t['flags']
            if 'must_fail' in t:
                test.must_fail = t['must_fail']
            if 'expects_failure' in t:
                test.expects_failure = t['expects_failure']

            if not test.checks:
                test.checks.append(test.check.name)

            check.tests.append(test)

    return check

def find_qt_installation(major_version, qmakes):
    installation = QtInstallation()

    for qmake in qmakes:
        qmake_version_str,success = get_command_output(qmake + " -query QT_VERSION")
        if success and qmake_version_str.startswith(str(major_version) + "."):
            qmake_header_path = get_command_output(qmake + " -query QT_INSTALL_HEADERS")[0].strip()
            if qmake_header_path:
                installation.qmake_header_path = qmake_header_path
                installation.int_version = int(qmake_version_str.replace(".", ""))
                if _verbose:
                    print "Found Qt " + str(installation.int_version) + " using qmake " + qmake
            break

    if installation.int_version == 0 and major_version >= 5: # Don't warn for missing Qt4 headers
        print "Error: Couldn't find a Qt" + str(major_version) + " installation"
    return installation

def libraryName():
    if _platform == 'win32':
        return 'ClangLazy.dll'
    elif _platform == 'darwin':
        return 'ClangLazy.dylib'
    else:
        return 'ClangLazy.so'

def link_flags():
    flags = "-lQt5Core -lQt5Gui -lQt5Widgets"
    if _platform.startswith('linux'):
        flags += " -lstdc++"
    return flags

def more_clazy_args():
    return " -Xclang -plugin-arg-clang-lazy -Xclang no-inplace-fixits -Wno-unused-value -Qunused-arguments "

def compiler_command(qt):
    if 'CLAZY_CXX' in os.environ:
        return os.environ['CLAZY_CXX'] + more_clazy_args() + qt.compiler_flags()

    return "clang -std=c++14 -Xclang -load -Xclang " + libraryName() + " -Xclang -add-plugin -Xclang clang-lazy " + more_clazy_args() + qt.compiler_flags()

def dump_ast_command(test):
    return "clang -std=c++14 -fsyntax-only -Xclang -ast-dump -fno-color-diagnostics -c " + qt_installation(test.qt_major_version).compiler_flags() + " " + test.filename

def compiler_name():
    if 'CLAZY_CXX' in os.environ:
        return os.environ['CLAZY_CXX'] # so we can set clazy.bat instead
    return 'clang'

#-------------------------------------------------------------------------------
# Get clang version
version,success = get_command_output(compiler_name() + ' --version')

match = re.search('clang version (.*?)[ -]', version)
try:
    version = match.group(1)
except:
    print "Could not determine clang version, is it in PATH?"
    sys.exit(-1)

CLANG_VERSION = int(version.replace('.', ''))

#-------------------------------------------------------------------------------
# Global variables

_enable_fixits_argument = "-Xclang -plugin-arg-clang-lazy -Xclang enable-all-fixits"
_help_command = "echo | clang -Xclang -load -Xclang " + libraryName() + " -Xclang -add-plugin -Xclang clang-lazy -Xclang -plugin-arg-clang-lazy -Xclang help -c -xc -"
_dump_ast = "--dump-ast" in sys.argv
_verbose = "--verbose" in sys.argv
_help = "--help" in sys.argv
_num_threads = multiprocessing.cpu_count()
_lock = threading.Lock()
_was_successful = True
_qt5_installation = find_qt_installation(5, ["QT_SELECT=5 qmake", "qmake-qt5", "qmake"])
_qt4_installation = find_qt_installation(4, ["QT_SELECT=4 qmake", "qmake-qt4", "qmake"])
#-------------------------------------------------------------------------------
# utility functions #2

def qt_installation(major_version):
    if major_version == 5:
        return _qt5_installation
    elif major_version == 4:
        return _qt4_installation

    return None

def run_command(cmd, output_file = "", test_env = os.environ):
    lines,success = get_command_output(cmd, test_env)
    lines = lines.replace("std::_Container_base0", "std::_Vector_base") # Hack for Windows, we have std::_Vector_base in the expected data
    lines = lines.replace("std::_Vector_alloc", "std::_Vector_base")
    if not success and not output_file:
        print lines
        return False

    lines = lines.replace('\r\n', '\n')
    if output_file:
        f = open(output_file, 'w')
        f.writelines(lines)
        f.close()
    else:
        print lines

    return success

def print_usage():
    print "Usage for " + sys.argv[0].strip("./") + ":\n"
    print "    " + sys.argv[0] + " [--help] [--dump-ast] [check1,check2,check3]"
    print
    print "    Without any check supplied, all checks will be run."
    print "    --dump-ast is provided for debugging purposes.\n"
    print "Help for clang plugin:"
    print
    run_command(_help_command)

def files_are_equal(file1, file2):
    try:
        f = open(file1, 'r')
        lines1 = f.readlines()
        f.close()

        f = open(file2, 'r')
        lines2 = f.readlines()
        f.close()

        return lines1 == lines2
    except:
        return False

def get_check_names():
    return filter(lambda entry: os.path.isdir(entry), os.listdir("."))

# Returns all files with .cpp_fixed extension. These were rewritten by clang.
def get_fixed_files():
    return filter(lambda entry: entry.endswith('.cpp_fixed.cpp'), os.listdir("."))

def print_differences(file1, file2):
    return run_command("diff -Naur {} {}".format(file1, file2))

def extract_word(word, in_file, out_file):
    in_f = open(in_file, 'r')
    out_f = open(out_file, 'w')
    for line in in_f:
        if word in line:
            out_f.write(line)
    in_f.close()
    out_f.close()

def run_unit_test(test):
    qt = qt_installation(test.qt_major_version)

    if _verbose:
        print
        print "Qt version: " + str(qt.int_version)
        print "Qt headers: " + qt.qmake_header_path

    if qt.int_version < test.minimum_qt_version or qt.int_version > test.maximum_qt_version or CLANG_VERSION < test.minimum_clang_version:
        return True

    if _platform in test.blacklist_platforms:
        return True

    checkname = test.check.name
    filename = checkname + "/" + test.filename

    output_file = filename + ".out"
    result_file = filename + ".result"
    expected_file = filename + ".expected"

    compiler_cmd = compiler_command(qt)

    if test.link:
        cmd = compiler_cmd + " " + link_flags()
    else:
        cmd = compiler_cmd + " -c "

    if test.isScript():
        clazy_cmd = "./" + filename
    else:
        clazy_cmd = cmd + test.flags + " -Xclang -plugin-arg-clang-lazy -Xclang " + string.join(test.checks, ',') + " "
        if not test.isFixedFile: # When compiling the already fixed file disable fixit, we don't want to fix twice
            clazy_cmd += _enable_fixits_argument + " "
        clazy_cmd += filename

    if test.compare_everything:
        result_file = output_file

    if test.isFixedFile:
        result_file = filename

    if _verbose:
        print "Running: " + clazy_cmd

    must_fail = test.must_fail

    cmd_success = run_command(clazy_cmd, output_file, test.env)

    if (not cmd_success and not must_fail) or (cmd_success and must_fail):
        print "[FAIL] " + checkname + " (Failed to build test. Check " + output_file + " for details)"
        print
        return False

    if not test.compare_everything and not test.isFixedFile:
        word_to_grep = "warning:" if not must_fail else "error:"
        extract_word(word_to_grep, output_file, result_file)

    printableName = checkname
    if len(test.check.tests) > 1:
        printableName += "/" + test.filename

    success = files_are_equal(expected_file, result_file)

    if test.expects_failure:
        if success:
            print "[XOK]   " + printableName
        else:
            print "[XFAIL] " + printableName
            if not print_differences(expected_file, result_file):
                return False
    else:
        if success:
            print "[OK]   " + printableName
        else:
            print "[FAIL] " + printableName
            if not print_differences(expected_file, result_file):
                return False

    return True

def run_unit_tests(tests):
    result = True
    for test in tests:
        result = result and run_unit_test(test)

    global _was_successful, _lock
    with _lock:
        _was_successful = _was_successful and result

def dump_ast(check):
    for test in check.tests:
        run_command(dump_ast_command(test) + " > " + test.filename + ".ast")
#-------------------------------------------------------------------------------
def load_checks(all_check_names):
    checks = []
    for name in all_check_names:
        try:
            check = load_json(name)
            if check.enabled:
                checks.append(check)
        except:
            print "Error while loading " + name
            raise
            sys.exit(-1)
    return checks
#-------------------------------------------------------------------------------
# main

if _help:
    print_usage()
    sys.exit(0)

args = sys.argv[1:]

switches = ["--verbose", "--dump-ast", "--help"]

if _dump_ast:
    del(args[args.index("--dump-ast")])

os.environ['CLAZY_CHECKS'] = ''

all_check_names = get_check_names()
all_checks = load_checks(all_check_names)
requested_check_names = filter(lambda x: x not in switches, args)
requested_check_names = map(lambda x: x.strip("/\\"), requested_check_names)

for check_name in requested_check_names:
    if check_name not in all_check_names:
        print "Unknown check: " + check_name
        print
        sys.exit(-1)

if not requested_check_names:
    requested_check_names = all_check_names

requested_checks = filter(lambda check: check.name in requested_check_names, all_checks)
requested_checks = filter(lambda check: check.minimum_clang_version <= CLANG_VERSION, requested_checks)

threads = []

if _dump_ast:
    for check in requested_checks:
        os.chdir(check.name)
        dump_ast(check)
        os.chdir("..")
else:
    list_of_chunks = [[] for x in range(_num_threads)]  # Each list is a list of Test to be worked on by a thread
    i = _num_threads
    for check in requested_checks:
        for test in check.tests:
            if not test.isFixedFile:
                i = (i + 1) % _num_threads

            list_of_chunks[i].append(test)

    for tests in list_of_chunks:
        if not tests:
            continue;

        t = Thread(target=run_unit_tests, args=(tests,))
        t.start()
        threads.append(t)

for thread in threads:
    thread.join()

sys.exit(0 if _was_successful else -1)
