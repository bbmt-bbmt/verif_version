#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from win32api import GetFileVersionInfo, LOWORD, HIWORD
import sys
import pywintypes
import os
import configparser
import pycurl
# import pathlib
# import ctypes
from io import BytesIO
import subprocess
import colorama
from colorama import Fore
colorama.init()

download_name = ""


def read_verif_version_ini():
    try:
        config = configparser.ConfigParser()
        config.read("verif_version.ini", encoding="utf-8-sig")
    except configparser.Error:
        print("erreur lors de l'initialisation du fichier ini : ")
        raise SystemExit(0)
    dictionary = {section: dict(config.items(section)) for section in config.sections()}
    return dictionary


def get_version_number(filename):
    try:
        info = GetFileVersionInfo(filename, "\\")
        ms = info['FileVersionMS']
        ls = info['FileVersionLS']
        list_version = [str(HIWORD(ms)), str(LOWORD(ms)), str(HIWORD(ls)), str(LOWORD(ls))]
        result = ".".join([str(i) for i in list_version])
    except pywintypes.error:
        result = "aucune version disponible"
    return result


def init_proxy(curl, proxy):
    try:
        curl.setopt(curl.PROXY, proxy['ip'].strip())
        curl.setopt(curl.PROXYPORT, int(proxy['port']))
        #curl.setopt(curl.PROXYTYPE, curl.PROXYTYPE_HTTP)
        if proxy['auth'].strip() == 'ntlm':
            curl.setopt(curl.PROXYAUTH, curl.HTTPAUTH_NTLM)
            curl.setopt(pycurl.PROXYUSERNAME, '')
            curl.setopt(pycurl.PROXYPASSWORD, '')
        else:
            curl.setopt(curl.PROXYAUTH, curl.HTTPAUTH_BASIC)
            curl.setopt(curl.PROXYUSERPWD, "%s:%s" % (proxy['login'], proxy['pass']))
    except KeyError:
        raise SystemExit("erreur lors de l'initialisation du proxy")
    return


def progress(total_to_download, total_downloaded, total_to_upload, total_uploaded):
    global download_name
    percent_completed = 0
    if total_to_download:
        percent_completed = total_downloaded * 100 // total_to_download
        sys.stdout.write('\r%s: %s%%   ' % (download_name, percent_completed))
        sys.stdout.flush()

def init_curl(curl):
    curl.setopt(pycurl.SSL_VERIFYPEER, 0)
    curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    #curl.setopt(curl.USERAGENT, 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0')
    curl.setopt(curl.FOLLOWLOCATION, 1)
    #curl.setopt(curl.HTTPHEADER, ["Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language: fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3"])
    #curl.setopt(curl.HTTPHEADER, ["Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language: fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3", 
    #                              "Accept-Encoding: gzip, deflate",
    #                              "Cookie:oraclelicense=accept-securebackup-cookie"])
    #curl.setopt(curl.VERBOSE, 1)
    return

def download_file(link, proxy=None):
    file_name = link.split('/')[-1]
    curl = pycurl.Curl()
    init_curl(curl)
    #curl.setopt(curl.SSL_VERIFYPEER, 0)
    #curl.setopt(curl.SSL_VERIFYHOST, 0)
    curl.setopt(curl.NOPROGRESS, False)
    curl.setopt(curl.XFERINFOFUNCTION, progress)
    curl.setopt(curl.URL, link)
    #curl.setopt(curl.USERAGENT, 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0')
    #curl.setopt(curl.COOKIEFILE, '')
    curl.setopt(curl.HTTPHEADER, ["Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language: fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3", 
                                  "Accept-Encoding: gzip, deflate",
                                  "Cookie:oraclelicense=accept-securebackup-cookie"])
    #curl.setopt(curl.FOLLOWLOCATION, 1)
    #curl.setopt(curl.VERBOSE, 1)
    if proxy is not None:
        init_proxy(curl, proxy)
    with open(file_name, 'wb') as f:
        curl.setopt(curl.WRITEDATA, f)
        curl.perform()
        curl.close()
    return file_name


def get_page(link, proxy=None):
    curl = pycurl.Curl()
    #curl.setopt(pycurl.SSL_VERIFYPEER, 0)
    #curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    init_curl(curl)
    curl.setopt(curl.URL, link)

    #curl.setopt(curl.USERAGENT, 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0')
    #curl.setopt(curl.COOKIEFILE, '')
    curl.setopt(curl.HTTPHEADER, ["Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language: fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3"])
    #curl.setopt(curl.VERBOSE, 1)

    buf_bytes = BytesIO()
    curl.setopt(curl.WRITEDATA, buf_bytes)
    if proxy is not None:
        init_proxy(curl, proxy)
    curl.perform()
    page_bytes = buf_bytes.getvalue()
    page = page_bytes.decode("utf-8", "replace")
    curl.close()
    return page


class Prog:
    def __init__(self, name, **param):
        self.name = name
        try:
            self.version_link = param['version_link'].strip()
            self.version_regex = param.get('version_regex', '').strip()
            self.download_regex = param.get('download_regex', '').strip()
            self.download_link = param.get('download_link', self.version_link).strip()
            self.cmd = param['cmd'].strip()
            self.version = None
            self.to_download = False
        except KeyError:
            print("Erreur: il manque des paramètres")
            raise SystemExit(-1)
        return

    def get_remote_version(self, proxy=None):
        global download_name
        if self.version_regex == '':
            download_name = self.name
            file_name = download_file(self.version_link, proxy)
            version = get_version_number(file_name)
            sys.stdout.write("\r")
        else:
            page = get_page(self.version_link, proxy)
            reg = re.search(self.version_regex, page)
            try:
                version = reg.groups()[0].strip().lower()
            except AttributeError:
                version = "aucune version disponible"
        print(self.name + ":", version)
        self.version = version
        return

    def get_host_version(self):
        version = ''
        subprocess.call(self.cmd + ' 1>cmdcall.txt 2>&1', shell=True, creationflags=subprocess.SW_HIDE)
        with open('cmdcall.txt', "r") as f:
            version = ''.join(f.readlines())
        return version.lower()

    def run_cmp(self):
        if self.version not in self.get_host_version() or self.version == "aucune version disponible" or self.version is None:
            print(Fore.LIGHTRED_EX + self.name + " doit être mis à jour" + Fore.RESET)
            # si on n'a pas donné un version_regex
            # c'est qu'on a déja téléchargé l'exe pour vérifier la version
            # donc pas besoin de le retélécharger
            if self.version_regex != '':
                self.to_download = True
        else:
            print(Fore.LIGHTGREEN_EX + self.name + " est à jour" + Fore.RESET)
        pass

    def dowload_installer(self, proxy=None):
        global download_name
        if self.to_download is False:
            return
        if self.download_regex != '':
            page = get_page(self.download_link, proxy)
            # regex = self.download_regex.replace('VERSION', self.version)
            reg_result = re.search(self.download_regex, page)
            try:
                download_link = reg_result.groups()[0]
            except:
                print("le lien de téléchargement n'est pas dans la page")
                return
        else:
            # si on ne donne pas de regex pour trouver le lien dans la page
            # c'est que download_link correspond aux lien de téléchargement
            # on remplace juste VERSION par self.version
            download_link = self.download_link.replace('VERSION', self.version)

        download_name = self.name
        download_file(download_link, proxy)
        print()
        return


def main():
    # efface l'écran
    print('\x1b[2J', end='')

    conf = read_verif_version_ini()
    list_prog = []
    proxy = None
    for name, param in conf.items():
        if name == 'Proxy':
            proxy = param
            continue
        list_prog.append(Prog(name, **param))
    print(Fore.LIGHTMAGENTA_EX + "version disponible sur internet:" + Fore.RESET)
    for p in list_prog:
        try:
            p.get_remote_version(proxy=proxy)
        except pycurl.error as p:
            print(p)

    print()

    for p in list_prog:
        p.run_cmp()

    print()
    print(Fore.LIGHTMAGENTA_EX + "Téléchargements des mises à jour:" + Fore.RESET)
    for p in list_prog:
        p.dowload_installer(proxy=proxy)

    print(Fore.LIGHTMAGENTA_EX + "Téléchargements terminés" + Fore.RESET)
    os.system('pause')

#    if sys.argv[1:] and sys.argv[1] == "messagebox":
#        intro_message = 'Des mises à jour sont dispo :\n'
#        message = ''
#        for p in list_prog:
#            if p.to_download is True:
#                message += p.name + '-'
#        if message != '':
#            ctypes.windll.user32.MessageBoxW(0, intro_message + message, "Mises à jour", 0)

    return

if __name__ == '__main__':
    main()
