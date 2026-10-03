project('ctp-native-probe', 'cpp', default_options: ['cpp_std=c++17', 'b_vscrt=mt'])
py = import('python').find_installation(get_option('python'))
cpp = meson.get_compiler('cpp')
pybind_include = run_command(py, '-c', 'import pybind11; print(pybind11.get_include())', check: true).stdout().strip()
pybind_flag = cpp.get_id() in ['msvc', 'clang-cl'] ? '/I' : '-I'
if cpp.get_id() in ['msvc', 'clang-cl']
  add_project_arguments('/utf-8', '/D_CRT_SECURE_NO_WARNINGS', language: 'cpp')
endif
py.extension_module('_native_probe', 'probe.cpp',
  include_directories: include_directories('../../../native'),
  cpp_args: [pybind_flag + pybind_include],
  dependencies: [py.dependency(), dependency('threads')],
  install: false,
)
