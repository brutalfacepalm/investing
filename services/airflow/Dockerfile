FROM apache/airflow:slim-latest-python3.10

USER root
WORKDIR /opt/airflow/
RUN mkdir -p logs dags plugins
RUN chmod -R 777 logs dags plugins

#   cd /tmp && git clone https://github.com/edenhill/librdkafka.git && \
#   cd librdkafka && git checkout tags/v2.0.2 && \
#   ./configure && make && make install && \
#   cd ../ && rm -rf librdkafka

RUN apt-get update -y
#  && apt-get upgrade -y
RUN apt-get install -yf nano
# RUN apt-get update -y && apt-get install -y gcc && apt-get install -y --no-install-recommends gcc git libssl-dev g++ make

### Install Google Chrome
RUN apt-get install -yf wget xvfb unzip
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
RUN apt-get update -y
RUN apt-get install -y google-chrome-stable

### Install ChromeDriver
RUN apt-get install -yqq unzip
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
RUN unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/
RUN chmod 777 /usr/local/bin/chromedriver
RUN chmod 777 /usr/bin/google-chrome

# RUN export PATH=$PATH:~/.local/bin
# RUN ls -l
# RUN chmod -R 777 /home/airflow/.local/bin
# RUN chmod -R 777 /.local

USER airflow

RUN pip install psycopg2-binary>=2.8.0 --user
RUN pip install pandas>=1.5.3 --user
RUN pip install --upgrade requests --user
RUN pip install apache-airflow==2.6.1 --user
RUN pip install confluent-kafka==2.0.2 --user
RUN pip install airflow-provider-kafka==0.2.2 --user
RUN pip install apache-airflow-providers-mongo==3.0.0 --user
RUN pip install apache-airflow-providers-postgres==5.5.2 --user
RUN pip install apache-airflow-providers-common-sql>=1.3.1
RUN pip install holidays==0.14.2 --user
RUN pip install numba==0.56.4 --user
RUN pip install torch==2.0.1 --user
RUN pip install numpy==1.23.5 --user
RUN pip install scikit-learn==1.2.2 --user
RUN pip install selenium==4.10.0 --user
RUN pip install webdriver_manager --user

