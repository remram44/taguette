import io
import os
from setuptools import setup


os.chdir(os.path.abspath(os.path.dirname(__file__)))


with io.open('README.rst', encoding='utf-8') as fp:
    description = fp.read()
req = [
    'tornado>=5.0',
    'sqlalchemy',
    'bcrypt',
    'jinja2',
    'beautifulsoup4',
    'bleach',
]
setup(name='qualtag',
      version='0.0',
      packages=['tagger'],
      entry_points={
          'console_scripts': [
              'qualtag = tagger.web:main']},
      install_requires=req,
      description="Document tagger",
      author="Remi Rampin",
      author_email='remirampin@gmail.com',
      maintainer="Remi Rampin",
      maintainer_email='remirampin@gmail.com',
      url='https://gitlab.com/remram44/nocturnal-retriever',
      project_urls={
          'Homepage': 'https://gitlab.com/remram44/nocturnal-retriever',
          'Say Thanks': 'https://saythanks.io/to/remram44',
          'Source': 'https://gitlab.com/remram44/nocturnal-retriever',
          'Tracker': 'https://gitlab.com/remram44/nocturnal-retriever/issues',
      },
      long_description=description,
      license='BSD-3-Clause',
      keywords=['qualitative', 'document', 'text', 'tagging', 'tags',
                'highlights', 'notes'],
      classifiers=[
          'Development Status :: 2 - Pre-Alpha',
          'Environment :: Web Environment',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: BSD License',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: JavaScript',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Scientific/Engineering :: Information Analysis',
          'Topic :: Scientific/Engineering :: Visualization',
          'Topic :: Text Processing'])
