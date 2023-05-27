FROM apache/airflow:2.4.3-python3.8

RUN mkdir lags dags plugins
USER root
RUN apt-get update -y && apt-get install -y gcc && \
  apt-get install -y --no-install-recommends gcc git libssl-dev g++ make && \
  cd /tmp && git clone https://github.com/edenhill/librdkafka.git && \
  cd librdkafka && git checkout tags/v2.0.2 && \
  ./configure && make && make install && \
  cd ../ && rm -rf librdkafka
USER airflow

RUN pip install apache-airflow[azure]
RUN pip install confluent-kafka==2.0.2
RUN pip install airflow-provider-kafka==0.2.2
RUN pip install apache-airflow-providers-mongo==3.0.0
RUN pip install holidays==0.14.2
RUN pip install numba==0.56.4
RUN pip install torch==2.0.1
RUN pip install numpy==1.23.5
RUN pip install scikit-learn
