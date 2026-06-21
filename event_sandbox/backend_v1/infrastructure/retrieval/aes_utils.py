# -*- coding: utf-8 -*-
import base64
from Crypto.Cipher import AES


class AESCrypt:
    def __init__(self, key, model="ECB", iv="", encode_="utf-8"):
        self.encode_ = encode_
        self.model = {"ECB": AES.MODE_ECB, "CBC": AES.MODE_CBC}[model]
        self.key = self.add_16(key)
        if model == "ECB":
            self.aes = AES.new(self.key, self.model)
        elif model == "CBC":
            self.aes = AES.new(self.key, self.model, iv)

    def add_16(self, par):
        par = par.encode(self.encode_)
        while len(par) % 16 != 0:
            par += b"\x00"
        return par

    def aesencrypt(self, text):
        text = self.add_16(text)
        self.encrypt_text = self.aes.encrypt(text)
        return base64.encodebytes(self.encrypt_text).decode().strip()

    def aesdecrypt(self, text):
        text = base64.decodebytes(text.encode(self.encode_))
        self.decrypt_text = self.aes.decrypt(text)
        return self.decrypt_text.decode(self.encode_).strip("\0")
