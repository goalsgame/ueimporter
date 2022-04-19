from setuptools import setup, find_packages

setup(name='ueimporter',
      version='0.1.0',
      description='Imports Unreal Engine releases into plastic repository',
      url='http://github.com/goalsgame/tools-game-utils/ueimporter',
      author='Andreas Andersson',
      author_email='andersson@goals.co',
      licence_files = ('LICENSE-MIT', 'LICENSE-APACHE'),
      license_="MIT/Apache-2.0",
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'License :: OSI Approved :: Apache Software License',
      ],
      packages=find_packages(),
      zip_safe=False,
      entry_points={
          'console_scripts': ['ueimporter=ueimporter.main:main'],
      },
      setup_requires=['pytest-runner'],
      tests_require=['pytest'],
      python_requires='>=3.9.0',
      )
