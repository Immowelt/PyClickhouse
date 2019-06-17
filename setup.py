from setuptools import setup

REQUIRED=['requests', 'future', 'six', 'ujson']

setup(name='pyclickhouse',
      version='0.8.2',
      description='Minimalist Clickhouse Python driver with an API roughly resembling Python DB API 2.0 specification.',
      url='https://github.com/Immowelt/PyClickhouse',
      download_url = 'https://github.com/Immowelt/PyClickhouse/archive/0.8.2.tar.gz',
      keywords = ['Clickhouse', 'Database', 'Driver'],
      classifiers=[],
      author='Immowelt AG',
      author_email='m.fridental@immowelt.de',
      license='Apache2',
      packages=['pyclickhouse'],
      install_requires=REQUIRED,
      use_2to3=True,
      test_suite='test',
      zip_safe=False)

