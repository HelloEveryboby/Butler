from setuptools import setup, find_packages

setup(
    name="Butler",
    version="2.1.0",
    description="一种基于Python的高级智能助手系统",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.32.0",
        "python-dotenv",
        "PyYAML",
        "pydantic",
        "redis",
        "watchdog",
        "psutil"
    ],
    entry_points={
        'console_scripts': [
            'butler=Butler:main',
        ],
    },
)
