import os

# --- config file process functions ------------
# these functions is for processing config file
# ----------------------------------------------
def read_list_from_section(section):
    # first,get size
    size = int(section["size"])
    ret = list()
    for i in range(0,size):
        ret.append(section[str(i)])
    return ret

def write_list_to_section(section,l):
    section["size"] = str(len(l))
    for i in range(0,len(l)):
        section[str(i)] = str(l[i])

def load_config_file(config_file):
    from configparser import ConfigParser
    config = ConfigParser()
    config.read(config_file)

    # processing input and output config
    ret = dict()
    for l in ['file_input','file_output']:
        if l in config:
            ret[l]=read_list_from_section(config[l])

    # process other part of config
    part = ['IO','Other']
    for i in part:
        if i in config:
            ret.update(config[i])

    # converse some element to correct type
    if 'timeout' in ret:
        ret['timeout'] = int(ret['timeout'])

    return ret

def save_config_file(config_file,args):
    from configparser import ConfigParser
    config = ConfigParser()

    for l in ['file_input','file_output']:
        if l in args and args[l] != None:
            config[l] = {}
            write_list_to_section(config[l],args[l])

    config['IO'] = {}
    config['Other'] = {}

    # processing IO related info
    io = ['std_input','std_output','arg_input','test_case_dir']
    for i in io:
        if i in args and args[i] != None: # check args[i] isn't None
            config['IO'][i] = str(args[i])

    # processing other info
    other = ['timeout','command']
    for i in other:
        if i in args and args[i] != None: # check args[i] isn't None
            config['Other'][i] = str(args[i])

    configfile = open(config_file,'w')
    config.write(configfile)
    configfile.close()

# --- functions about test case -----------------------
# These functions is about test case.
# Cjudge will try to guess the name of each test case,
# basing on `std_input`,`file_intput` and so on.
# And that's what these functions do.
# ------------------------------------------------------
def output_struct_of_test_case(struct):
    from colorama import init,deinit,Fore
    init()
    print('Test Case Structure:')
    color_flag = 0
    for (k,v) in struct_of_test_case.items():
        if color_flag:
            print(Fore.YELLOW,end="")
        else:
            print(Fore.CYAN,end="")
        print(k.ljust(15),end="")
        print(v)
        color_flag = 1 - color_flag
    print(Fore.RESET)
    deinit()

def parse_structure_of_test_case(args):
    "parse test case structure"
    accepted_flags = ["file_input","std_input","arg_input",
                      "file_output","std_output"]
    result = dict()
    for (flag,value) in args.items():
        if flag in accepted_flags and value != None:
                result[flag] = value

    return result

def try_insert_test_case(t,v,file_name,test_cases):
    pre,end = os.path.splitext(v)
    if file_name.startswith(pre) and file_name.endswith(end):
        # insert (file_name,pre+end) into test_cases[test_casename]
        # pre+end is the name which this file should be renamed to
        # when using this file as test data.
        # file_name[len(pre):-len(end)] is the name of the test case
        # "input" or "output" means the file is for input or output
        test_cases.setdefault(file_name[len(pre):-len(end)],
                              {"input":list(),"output":list()}
                              )[t].append(
                                  (os.path.abspath(file_name),pre+end))

def get_test_cases_by_parse_dir(test_case_dir,recursive,structure):
    "parse name of the test_case_dir to find out all test cases"
    old_cwd = os.getcwd() # save old cwd
    os.chdir(test_case_dir)

    test_cases = dict()
    for file_or_dir in os.listdir(os.getcwd()):
        if os.path.isfile(file_or_dir):
            for (k,value) in structure.items():
                t = "input" if k.find("input") != -1 else "output"
                if isinstance(value,list):
                    for v in value:
                        try_insert_test_case(t,v,
                                             file_or_dir,test_cases)
                else:
                    try_insert_test_case(t,value,
                                         file_or_dir,test_cases)
        elif recursive:
            test_cases.update(get_test_cases_by_parse_dir(file_or_dir,
                                                          recursive,
                                                          structure))

    os.chdir(old_cwd)
    return test_cases

# --- judge related functions --------------------
# These functions will prepare datas for test,
# run the program and judge whether it is correct.
# ------------------------------------------------
def prepare_data(data):
    "copy datas to current working directory and rename it"
    for (file_name,dst_name) in data["input"]:
        if os.path.abspath(file_name) == os.path.abspath(dst_name):
            continue # file_name and dst_name refer the same file
        # copy file
        try:
            src = open(file_name,'rb')
            dst = open(dst_name,'wb')
            dst.write(src.read())
            dst.close()
            src.close()
        except:
            print('\n!!!Error occured when preparing %s'%file_name)
            return False
    return True

def run_and_judge(name,struct,timeout,command,data):
    "running program"
    # prepare datas for running
    targs = []
    if "arg_input" in struct:
        targs = open(struct["arg_input"],"r").read().split()
    tstdin = None
    if "std_input" in struct:
        tstdin = open(struct["std_input"],"r")
    import tempfile
    tstdout = tempfile.TemporaryFile(mode='w+')

    errs = []
    from subprocess import call,TimeoutExpired
    targs.append(command)
    try:
        exitcode = call(targs,stdin=tstdin,stdout=tstdout,timeout=timeout)
    except TimeoutExpired:
        errs.append("!!!Time Limit Exceeded!!!")

    # compare stdout and answer
    tstdout.seek(0)
    tstdout_content = tstdout.read()
    ans_stdout = ""
    if "std_output" in struct:
        for (path,dst) in data["output"]:
            if dst == struct["std_output"]:
                ans_stdout = open(path,'r').read()

    if tstdout_content != ans_stdout:
        errs.append("!!!Standard output mismatched!")
        errs.append("program output saved in %s"%
                    ('%s.cjudge.stdout.txt'%name))
        open('%s.cjudge.stdout.txt'%name,"w").write(tstdout_content)
        return False,exitcode,errs

    # compare file output and answer
    file_output_ok = True
    for (ans,t) in data["output"]:
        if t in struct["file_output"]:
            t1 = open(ans).read()
            t2 = open(t).read()
            if t1 != t2:
                file_output_ok = False
                errs.append("!!!%s mismatched"%t)
    if not file_output_ok:
        return False,exitcode,errs

    return True,exitcode,errs

# --- cjudge main program ---
def parse_sys_arg():
    "parse system arguments and return"
    # --- generate arguemtn parser ---
    import argparse
    arg_parser = argparse.ArgumentParser(
        description='cjudge is a offline judge tool',
        prog='cjudge')

    # input/output file settings
    arg_parser.add_argument('--file-input', action='append',
                            help='input file name')
    arg_parser.add_argument('--std-input',
                            help='standard input file name')
    arg_parser.add_argument('--arg-input',
                            help='arguments input file name')
    arg_parser.add_argument('--file-output', action='append',
                            help='output file name')
    arg_parser.add_argument('--std-output',
                            help='standard output file name')
    arg_parser.add_argument('--test-case-dir',
                            help='directory which contains test cases')
    arg_parser.add_argument('-r','-R','--recursive', action='store_true',
                            help='recursive parse test case directory')
    arg_parser.add_argument('--command',
                            help='command to running the program which will be tested')
    arg_parser.add_argument('--timeout',type=int,
                            help='terminate the command after *timeout* seconds')
    arg_parser.add_argument('-c','--config',
                            help='specific the name of config file')
    arg_parser.set_defaults(timeout = 1,
                            config='cjudge.conf.ini',
                            test_case_dir=os.getcwd())

    return arg_parser.parse_args()

def config_update(config,args):
    # chekc if user input argument
    possible_arg = ['std_input','file_input','arg_input',
                    'std_output','file_output','command']
    check = False
    for i in possible_arg:
        if i in args and args[i] != None:
            check = True
            break
    if check:
        config.update(args)

# start from here
args = vars(parse_sys_arg())
config = load_config_file(args['config'])
config_update(config,args)
args.update(config)
save_config_file(args['config'],args)

struct_of_test_case = parse_structure_of_test_case(args)
output_struct_of_test_case(struct_of_test_case)

test_cases = get_test_cases_by_parse_dir(args["test_case_dir"],
                                        args["recursive"],
                                        struct_of_test_case)

# for color output
from colorama import init,deinit,Fore
init()
# running each test case
stat_pass = 0
stat_failed = 0
failed_test_case_name = []
for (name,data) in test_cases.items():
    print('Test Case %s -> '%(Fore.YELLOW + name + Fore.RESET),end="")
    # prepare data
    print('Preparing test data ',end="")
    print(Fore.RED,end="") # highlight when there are error messages
    pd_sucess = prepare_data(data)
    print(Fore.RESET,end="")
    print('[%s]'%(Fore.GREEN +
                  ('Finish' if pd_sucess else 'Failed') +
                  Fore.RESET), end="")
    # testing
    print(' -> Testing ',end="")
    status,exitcode,errs = run_and_judge(name,
                                    struct_of_test_case,
                                    args['timeout'],args['command'],
                                    data)
    print("[%s]"%(Fore.YELLOW+'exitcode %d'%exitcode+Fore.RESET),end="")
    print(Fore.RED,end="")
    if errs :
        print("") # new line for pretty output
    for err in errs:
        print(err)
    print(Fore.RESET,end="")
    if status:
        stat_pass += 1
        print(' -> [ %s ]'%(Fore.GREEN +'PASS'+Fore.RESET))
    else:
        stat_failed += 1
        failed_test_case_name.append(name)
        print('>----- [ %s ] -----<\n'%(Fore.RED +'FAILED'+Fore.RESET))

# output final result
print('============= [ %s ] ============='%(Fore.CYAN +
                                            'Statistics' +
                                            Fore.RESET))
print('TOTAL: %s  PASS: %s  FAILED: %s'%(
    (Fore.YELLOW + str(stat_pass+stat_failed) + Fore.RESET),
    (Fore.GREEN + str(stat_pass) + Fore.RESET),
    (Fore.RED + str(stat_failed) + Fore.RESET)))
if failed_test_case_name:
    print('Failed test case name:')
    odd_line = True
    for i in failed_test_case_name:
        if odd_line:
            print(Fore.YELLOW,end="")
        else:
            print(Fore.CYAN,end="")
        print('   %s'%i)
    print(Fore.RESET)

deinit()
