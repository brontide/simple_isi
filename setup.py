from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='simple_isi',
      version='0.3',
      description='Bare-bones json interaction with EMC Isilon clusters',
      long_description=readme(),
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7.5',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
      ],
      keywords='isilon onefs',
      url='http://github.com/brontide/simple_isi',
      author='Eric Warnke',
      author_email='ericew@gmail.com',
      license='MIT',
      packages=['simple_isi'],
      install_requires=[
          'requests',
          'PyYAML',
          'future',
      ],
      entry_points={
          'console_scripts': ['isicmd=simple_isi.cmd:main'],
      },
      include_package_data=True,
      zip_safe=False)
