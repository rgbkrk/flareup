FROM python:3-onbuild

# libcurl4 for pycurl and the AsyncHTTPClient
RUN apt-get install libcurl4-openssl-dev -y

CMD ["python", "./app.py"]
