project(
  'vnpy_ctp', 'cpp',
  version: '6.7.11.4+ccxtproxy.3',
  license: 'MIT',
  meson_version: '>=1.7.0',
  default_options: ['buildtype=release', 'cpp_std=c++17', 'b_vscrt=mt'],
)

py = import('python').find_installation(pure: false)
cpp = meson.get_compiler('cpp')
root = meson.project_source_root()
system = host_machine.system()
architecture = host_machine.cpu_family()
pybind_include = run_command(py, '-c', 'import pybind11; print(pybind11.get_include())', check: true).stdout().strip()
pybind_flag = cpp.get_id() in ['msvc', 'clang-cl'] ? '/I' : '-I'
headers = 'native/include'
rpath = ''

if system == 'linux'
  if architecture != 'x86_64'
    error('The pinned Linux CTP library supports x86_64 only')
  endif
  ctp_dir = root / 'vendor/ctp/linux-x86_64'
  ctp = cpp.find_library('thosttraderapi_se', dirs: [ctp_dir], required: true)
  install_data(ctp_dir / 'libthosttraderapi_se.so', install_dir: py.get_install_dir() / 'vnpy_ctp/api')
  rpath = '$ORIGIN'
elif system == 'windows'
  if architecture != 'x86_64'
    error('The pinned Windows CTP library supports x86_64 only')
  endif
  if cpp.get_id() not in ['msvc', 'clang-cl']
    error('The vendor CTP C++ ABI requires an MSVC-compatible compiler')
  endif
  ctp_dir = root / 'vendor/ctp/windows-x86_64'
  add_project_arguments('/utf-8', '/D_CRT_SECURE_NO_WARNINGS', language: 'cpp')
  ctp = cpp.find_library('thosttraderapi_se', dirs: [ctp_dir], required: true)
  install_data(ctp_dir / 'thosttraderapi_se.dll', install_dir: py.get_install_dir() / 'vnpy_ctp/api')
elif system == 'darwin'
  if architecture not in ['x86_64', 'aarch64']
    error('The pinned macOS CTP framework supports x86_64 and arm64 only')
  endif
  headers = 'native/include/mac'
  ctp_dir = root / 'vendor/ctp/macos'
  ctp = declare_dependency(link_args: ['-F' + ctp_dir, '-framework', 'thosttraderapi_se'])
  install_subdir('vendor/ctp/macos/thosttraderapi_se.framework', install_dir: py.get_install_dir() / 'vnpy_ctp/api')
  rpath = '@loader_path'
else
  error('This CTP distribution supports Linux, Windows and macOS only')
endif

py.extension_module(
  'vnctptd',
  'native/vnctptd.cpp',
  include_directories: include_directories('native', headers),
  cpp_args: [pybind_flag + pybind_include],
  dependencies: [py.dependency(), ctp, dependency('threads')],
  install: true,
  # meson-python 从构建目录装配 wheel，macOS 的构建产物也必须携带加载路径。
  build_rpath: system == 'darwin' ? rpath : '',
  install_rpath: rpath,
  subdir: 'vnpy_ctp/api',
)
py.install_sources('src/vnpy_ctp/__init__.py', subdir: 'vnpy_ctp')
py.install_sources('src/vnpy_ctp/api/__init__.py', subdir: 'vnpy_ctp/api')
