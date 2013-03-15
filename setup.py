import os

from setuptools import setup, find_packages


setup(name='chirpradio_echo',
      version='1.0.0',
      description="",
      long_description='',
      author='Kumar McMillan',
      author_email='kumar.mcmillan@gmail.com',
      license='Apache 2.0',
      url='',
      include_package_data=True,
      classifiers=[],
      entry_points="""
          [console_scripts]
          ch-echo = chirpradio_echo:main
          """,
      packages=find_packages(exclude=['tests']),
      install_requires=[ln.strip() for ln in
                        open(os.path.join(os.path.dirname(__file__),
                                          'requirements.txt'))
                        if not ln.startswith('#')])
