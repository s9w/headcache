# coding=utf-8
from setuptools import setup, find_packages
import headcache

setup(name='headcache',
      version=headcache.__version__,
      packages=find_packages(),
      package_data={
          'headcache': ['preview_style.css', 'style.qss']
      },
      include_package_data=True,
      entry_points={
          'console_scripts': [
              'headcache = headcache.headcache:main',
          ],
      },
      install_requires=["mistune", "watchdog", "PyQt", "whoosh"],
      author='Sebastian Werhausen',
      author_email="swerhausen@gmail.com",
      url='https://github.com/s9w/headcache',
      description="note-typing program.")
