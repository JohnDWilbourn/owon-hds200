from setuptools import setup, find_packages

setup(
    name="owonhds",
    version="1.0.0",
    description="Python interface for OWON HDS200 series handheld oscilloscopes",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="John David Wilbourn",
    url="https://github.com/JohnDWilbourn/owon-hds200",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pyserial>=3.5",
    ],
    extras_require={
        "plot": ["matplotlib>=3.5"],
        "fft":  ["matplotlib>=3.5", "numpy>=1.21"],
        "all":  ["matplotlib>=3.5", "numpy>=1.21"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Topic :: Scientific/Engineering",
    ],
)
