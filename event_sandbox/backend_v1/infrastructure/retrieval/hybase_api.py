# -*- coding: utf-8 -*-
from typing import Optional, List, Dict

from hybaseapi.TRSConnection import TRSConnection
from hybaseapi.ConnectParams import ConnectParams
from hybaseapi.SearchParams import SearchParams
from hybaseapi.OperationParams import OperationParams
from hybaseapi.TRSInputRecord import TRSInputRecord

from .aes_utils import AESCrypt
from datetime import datetime
import os


class HybaseApi:
    def __init__(self, hybase_config=None):
        if hybase_config is None:
            hybase_config = {
                "hybase_key": "Trsadmin19940802.",
                "hybase_host": "http://192.168.156.87:5555",
                "hybase_security_code": "Yu5iztekGyFOOp821JM8WQ=="
            }
        self._config = hybase_config
        self.get_base_params()

    def get_base_params(self):
        self._hybase_key = self._config.get("hybase_key", "")
        self._hybase_host = self._config.get("hybase_host", "")
        self._hybase_security_code = self._config.get("hybase_security_code", "")

        self._aes = AESCrypt(self._hybase_key)
        [self._username, self._password] = self._aes.aesdecrypt(self._hybase_security_code).split("\n")

    def hybase_executeInsert(self, InputRecord: Optional[List[Dict]] = None, database=""):
        hydb = TRSConnection(self._hybase_host, self._username, self._password, ConnectParams())

        record_list = []
        for Record in InputRecord:
            r = TRSInputRecord()
            for key in Record.keys():
                r.addColumn(key, Record[key])
            record_list.append(r)

        insertedNum = hydb.executeInsert(database, record_list, OperationParams())
        return insertedNum

    def hybase_executeDeleteQuery(self, database, query):
        hydb = TRSConnection(self._hybase_host, self._username, self._password, ConnectParams())
        deletedNum = hydb.executeDeleteQuery(database, query, SearchParams())
        return deletedNum

    def hybase_executeSelect(self, database, query, start=0, recordNum=10):
        hydb = TRSConnection(self._hybase_host, self._username, self._password, ConnectParams())
        resultSet = hydb.executeSelect(database, query, start, recordNum, SearchParams())
        return resultSet

    def hybase_vector_executeSelect(self, database, query, start=0, recordNum=10, vector_fields="vector"):
        param = SearchParams()
        # param.setSortMethod(f"RELEVANCE;-TIMESTAMP")
        param.setSortMethod(f"RELEVANCE;-{vector_fields}")

        hydb = TRSConnection(self._hybase_host, self._username, self._password, ConnectParams())
        resultSet = hydb.executeSelect(database, query, start, recordNum, param)
        return resultSet
