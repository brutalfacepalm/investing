from pendulum import datetime, from_format, duration
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.mongo.hooks.mongo import MongoHook
import pandas as pd
import pymongo
from pymongo.write_concern import WriteConcern
from contextlib import closing

from service_files.parser_data import Parser
import json
import re


with open('./dags/service_files/shares.json', 'r+') as f:
    shares = json.load(f)

with open('./dags/service_files/currencies.json', 'r+') as f:
    currencies = json.load(f)

with open('./dags/service_files/features.json', 'r+') as f:
    features = json.load(f)

MONGO_DB_NAME = 'investing'
MAX_LEN_DATA_COLLECTION_MONGO = 1680


class SkipConflictPostgresHook(PostgresHook):
    def insert_rows(self, table, rows, target_fields=None, commit_every=1000,
                    replace=False, resolve_conflict=None, **kwargs):
        """

        A generic way to insert a set of tuples into a table,
        a new transaction is created every commit_every rows
        :param table:
        :param rows:
        :param target_fields:
        :param commit_every:
        :param replace:
        :param resolve_conflict:
        :param kwargs:
        :return:
        """
        i = 0
        with closing(self.get_conn()) as conn:
            if self.supports_autocommit:
                self.set_autocommit(conn, False)

            conn.commit()

            with closing(conn.cursor()) as cur:
                for i, row in enumerate(rows, 1):
                    lst = []
                    for cell in row:
                        lst.append(self._serialize_cell(cell, conn))
                    values = tuple(lst)
                    sql = self._generate_insert_sql(table, values, target_fields, replace, **kwargs)
                    if resolve_conflict:
                        sql += f' ON CONFLICT ({resolve_conflict}) DO NOTHING'
                    self.log.debug("Generated sql: %s", sql)
                    # print(sql)
                    cur.execute(sql, values)
                    if commit_every and i % commit_every == 0:
                        conn.commit()
                        self.log.info("Loaded %s rows into %s so far", i, table)

            conn.commit()
        self.log.info("Done loading. Loaded a total of %s rows into %s", i, table)


def fn_mongodb_create_collection(**context):
    """

    :param context:
    :return:
    """
    try:
        hook = MongoHook(conn_id='mongodb_conn')
        client = hook.get_conn()
        db_name = context['db_name']
        db = client[db_name]
        for ticker_subdata in currencies + features:
            ticker_subdata = "".join(re.findall(r"(\w*)", ticker_subdata)).upper()
            if ticker_subdata in db.list_collection_names():
                db.drop_collection(ticker_subdata)

            db.create_collection(name=ticker_subdata,
                                 capped=True,
                                 size=2128 * MAX_LEN_DATA_COLLECTION_MONGO * 2,
                                 max=MAX_LEN_DATA_COLLECTION_MONGO * 2)
            collection = db[ticker_subdata]
            collection.create_index([("time", pymongo.DESCENDING)],
                                    background=True,
                                    unique=True)

    except Exception as e:
        print(f"Error connecting to MongoDB -- {e}")


def fn_get_metadata(**context):
    """

    :param context:
    :return:
    """
    try:
        hook = MongoHook(conn_id='mongodb_conn')
        client = hook.get_conn()
        db_name = context['db_name']
        db = client[db_name]
        if 'meta' in db.list_collection_names():
            collection = db['meta']
            meta_data = list(collection.find({}, projection={'_id': False}))
            return json.dumps(meta_data)

    except Exception as e:
        print(f"Error connecting to MongoDB -- {e}")


def fn_parse_subdata(execution_date, **context):
    """

    :param execution_date:
    :param context:
    :return:
    """
    meta = json.loads(context['meta'])
    meta = pd.DataFrame.from_dict(dict(zip(['id', 'name', 'code', 'market', 'url'],
                                           list(zip(*[list(v.values()) for v in meta])))))
    meta = meta[meta['market'].isin([5, 14, 17, 24, 45])]
    subdata = {}
    for ticker_subdata in currencies:
        date_start = '01.01.2012 00:00:00'
        date_end = execution_date.in_timezone("Europe/Moscow").add(days=-1).strftime("%d.%m.%Y 23:00:00")

        parser_ticker = Parser(ticker_subdata,
                               date_start,
                               date_end,
                               split_period='year',
                               is_feature=False,
                               meta_df=meta,
                               subdata=True)
        data_as_df = parser_ticker.parse(code_name='name')
        subdata[ticker_subdata] = data_as_df

    for ticker_subdata in features:
        date_start = '01.01.2012 00:00:00'
        date_end = execution_date.in_timezone("Europe/Moscow").add(days=-1).strftime("%d.%m.%Y 23:00:00")

        parser_ticker = Parser(ticker_subdata.upper(),
                               date_start,
                               date_end,
                               split_period='year',
                               is_feature=False,
                               meta_df=meta,
                               subdata=True)
        data_as_df = parser_ticker.parse()
        subdata[ticker_subdata] = data_as_df

    return json.dumps(subdata)


def fn_mongodb_load_subdata(**context):
    """

    :param context:
    :return:
    """
    try:
        hook = MongoHook(conn_id='mongodb_conn')
        client = hook.get_conn()
        db_name = context['db_name']
        db = client[db_name]
        data = json.loads(context['parse_data'])
        for k, v in data.items():
            k = "".join(re.findall(r"(\w*)", k)).upper()
            to_insert = list(
                map(lambda x: dict(zip(['time', 'close'], x)), v))

            collection = db[k]
            collection.with_options(write_concern=WriteConcern(w=0)).insert_many(to_insert, ordered=False)

    except Exception as e:
        print(f"Error connecting to MongoDB -- {e}")


def fn_postgres_load_subdata(**context):
    """

    :param context:
    :return:
    """
    hook = SkipConflictPostgresHook(postgres_conn_id=context['postgres_conn_id'])
    data = json.loads(context['parse_data'])
    for k, v in data.items():
        k = "".join(re.findall(r"(\w*)", k)).upper()
        hook.insert_rows(table=k, rows=v, resolve_conflict='time')


default_args = {'start_date': datetime(2022, 12, 2, 15, tz="Europe/Moscow"),
                'retries': 5,
                'retry_delay': duration(seconds=15),}


with DAG(
        dag_id='002_init_subdata',
        default_args=default_args,
        schedule_interval=None
) as dag:
    postgres_create = PostgresOperator(
        task_id='postgres_create',
        postgres_conn_id="postgres_conn",
        sql='\n'.join(['DROP TABLE IF EXISTS {}; \n CREATE TABLE IF NOT EXISTS {} (time timestamp UNIQUE NOT NULL, close float);'.format("".join(re.findall(r"(\w*)", t)).upper(),
                                                                                                                                         "".join(re.findall(r"(\w*)", t)).upper()) for t in currencies + features]))
    mongo_create = PythonOperator(
        task_id="mongo_create",
        python_callable=fn_mongodb_create_collection,
        op_kwargs={'db_name': MONGO_DB_NAME})
    get_metadata = PythonOperator(
        task_id="get_metadata",
        python_callable=fn_get_metadata,
        op_kwargs={'db_name': MONGO_DB_NAME})
    parse_subdata = PythonOperator(
        task_id="parse_subdata",
        python_callable=fn_parse_subdata,
        op_kwargs={'meta': get_metadata.output})
    postgres_load_subdata = PythonOperator(
        task_id="postgres_load_subdata",
        python_callable=fn_postgres_load_subdata,
        op_kwargs={'postgres_conn_id': 'postgres_conn',
                   'parse_data': parse_subdata.output})
    mongodb_load_subdata = PythonOperator(
        task_id="mongodb_load_subdata",
        python_callable=fn_mongodb_load_subdata,
        op_kwargs={"parse_data": parse_subdata.output,
                   'db_name': MONGO_DB_NAME})


    [postgres_create, mongo_create] >> get_metadata >> parse_subdata >> [postgres_load_subdata, mongodb_load_subdata]
