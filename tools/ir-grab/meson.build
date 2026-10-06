project('ir-grab', 'cpp',
  version : '0.1.0',
  default_options : ['warning_level=2', 'cpp_std=c++17'])

libcamera_dep = dependency('libcamera', required : true)

executable('ir-grab',
  'ir_grab.cpp',
  dependencies : [libcamera_dep],
  install : true,
  install_dir : '/usr/libexec/howdy')
