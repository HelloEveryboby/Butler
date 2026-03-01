from setuptools import setup, find_packages

setup(
    name="Butler",
    version="2.0.0",
    description="一种基于Python的高级智能助手系统",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="PAYDAY3",
    author_email="error123456ew@outlook.com",
    url="https://github.com/PAYDAY3/Butler",
    packages=find_packages(),
    install_requires=[
        "pyttsx3",
        "pydub",
        "playsound",
        "pyaudio",
        "prompt_toolkit",
        "Pillow",
        "pygame",
        "watchdog",
        "python-dateutil",
        "sounddevice",
        "openpyxl",
        "python-docx",
        "PyPDF2",
        "requests>=2.32.0",
        "beautifulsoup4",
        "redis",
        "scrapy",
        "paramiko",
        "python-dotenv",
        "nltk",
        "pycryptodome",
        "schedule",
        "twisted>=24.7.0rc1",
        "numpy",
        "scipy"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Home Automation",
        "Topic :: Multimedia :: Sound/Audio :: Speech"
    ],
    python_requires='>=3.8',
    license="MIT",
    keywords="voice assistant, AI, home automation, Python",
    project_urls={
        "Documentation": "https://github.com/PAYDAY3/Butler/wiki",
        "Source": "https://github.com/PAYDAY3/Butler",
        "Tracker": "https://github.com/PAYDAY3/Butler/issues",
    },
    entry_points={
        'console_scripts': [
            'butler=butler.butler_app:main',
        ],
    },
    include_package_data=True,
    package_data={
        'butler': [
            'resources/*.wav'
        ]
    }
)
