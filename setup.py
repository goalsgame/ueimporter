from setuptools import setup, find_packages

setup(name='ueimporter',
      version='0.1',
      description='Imports Unreal Engine releases into plastic repository',
      url='http://github.com/goalsgame/tools-game-utils/ueimporter',
      author='Andreas Andersson',
      author_email='andersson@goals.co',
      license="Proprietary",
      classifiers=[
          'License :: Other/Proprietary License',
      ],
      packages=find_packages(),
      zip_safe=False,
      entry_points={
          'console_scripts': ['ueimporter=ueimporter.main:main'],
      }
      )
