#!/usr/bin/env python
# -*- coding: utf-8 -*-

# todo
# modification d'archi, le init de Prog devrait se charger tout seul
# de chercher les versions
# le main devrait juste creer les instances de Prog et puis peut être
# lancer download_installer. Il faut passer le proxy dans l'init de prog

import traceback
import re
from win32api import GetFileVersionInfo, LOWORD, HIWORD
import sys
import pywintypes
import os
import configparser
import pycurl
from io import BytesIO
import subprocess
import colorama
from colorama import Fore
colorama.init()

download_name = ""



def call_cmd(cmd):
    """ Permet de lancer des commandes indépendament du chemin
    C'est pour éviter les problèmes lorsque le fichier est dans un
    unc path
    """
    path = os.getcwd()
    # changer de repertoire permet de lancer pushd sans erreur
    os.chdir("c:\\")
    new_cmd = "pushd %s && %s && popd" % (path, cmd)
    # le pushd permet de changer de repertoire et de ne pas avoir
    # d'unc si on veut acceder à un fichier
    subprocess.call(new_cmd, shell=True, creationflags=subprocess.SW_HIDE, stderr=subprocess.DEVNULL)
    os.chdir(path)
    return


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
    try:
        if total_to_download:
            percent_completed = total_downloaded * 100 // total_to_download
            sys.stdout.write('\r%s: %s%%   ' % (download_name, percent_completed))
            sys.stdout.flush()
    except:
        # on retourne l'erreur 42 qui je croix correspond à un callbak error
        # ça va provoquer un raise pycurl.error
        return 5


def init_curl(curl):
    curl.setopt(pycurl.SSL_VERIFYPEER, 0)
    curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    # curl.setopt(curl.USERAGENT, 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0')
    curl.setopt(curl.FOLLOWLOCATION, 1)
    # curl.setopt(curl.VERBOSE, 0)
    return


def download_file(link, proxy=None,cookies=''):
    global download_name
    file_name = link.split('/')[-1]
    curl = pycurl.Curl()
    init_curl(curl)
    curl.setopt(curl.NOPROGRESS, False)
    curl.setopt(curl.XFERINFOFUNCTION, progress)
    curl.setopt(curl.URL, link)
    
    http_headers = ["Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language: fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Accept-Encoding: gzip, deflate"]
    if cookies:
        http_headers.append("Cookie:" + cookies)
    
    curl.setopt(curl.HTTPHEADER, http_headers)

    if proxy is not None:
        init_proxy(curl, proxy)
    try:
        with open(file_name, 'wb') as f:
            curl.setopt(curl.WRITEDATA, f)
            curl.perform()
    except BaseException as b:
        # on catch toutes les exceptions pour ne pas bloquer le programme
        # si un téléchargement se passe mal
        sys.stdout.write('\r%s: %s   ' % (download_name, str(b)))
        sys.stdout.flush()
        print()
        os.remove(file_name)
        # print("erreur: ", e)
    # except Exception as e:
    #     print(type(e))
    #     print("salut toi")
    finally:
        curl.close()
    return file_name


def get_page(link, proxy=None):
    curl = pycurl.Curl()
    init_curl(curl)
    curl.setopt(curl.URL, link)

    curl.setopt(curl.HTTPHEADER, ["Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                  "Accept-Language: fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3"])

    buf_bytes = BytesIO()
    curl.setopt(curl.WRITEDATA, buf_bytes)
    page = ''
    if proxy is not None:
        init_proxy(curl, proxy)
    try:
        curl.perform()
        page_bytes = buf_bytes.getvalue()
        page = page_bytes.decode("utf-8", "replace")
    except pycurl.error as e:
        print("erreur: ", e)
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
            self.cookies = param.get('cookies','').strip()
            self.cmd = param['cmd'].strip()
            self.version = None
            self.sous_version = None
            self.to_download = False
        except KeyError:
            print("Erreur: il manque des paramètres")
            call_cmd("pause")
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
                try:
                    self.sous_version = reg.groups()[1].strip().lower()
                except:
                    pass
            except AttributeError:
                version = "aucune version disponible"
        print(self.name + ":", version)
        self.version = version
        return

    def get_host_version(self):
        version = ''
        cmd = self.cmd + " 1>cmdcall.txt 2>&1 "

        call_cmd(cmd)

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
            reg_result = re.search(self.download_regex, page)
            try:
                download_link = reg_result.groups()[0]
            except:
                print("le lien de téléchargement n'est pas dans la page")
                return
        else:
            # si on ne donne pas de regex pour trouver le lien dans la page
            # c'est que download_link correspond aux lien de téléchargement
            # on remplace juste VERSION par self.version ou self.sous_version si il existe 
            # c'est pour flash j'ai besoin du 23 dans 23.0.0.162
            if self.sous_version:
                download_link = self.download_link.replace('VERSION', self.sous_version)
            else:
                download_link = self.download_link.replace('VERSION', self.version)


        download_name = self.name
        download_file(download_link, proxy, self.cookies)
        print()
        return


def erreur_final(*exc_info):
    # print(type(exc_info[1]))
    # print(exc_info[0]==KeyboardInterrupt)
    # les keyboardintterrup sont desactivés et géré dans le programme
    # text = "".join(traceback.format_exception(*exc_info))
    # print("execept", str(exc_info))
    # print(text)
    if exc_info[0] != KeyboardInterrupt:
        text = "".join(traceback.format_exception(*exc_info))
        print()
        print("Exception: %s" % text)
        call_cmd("pause")
        raise SystemExit(1)
    return


def main():
    sys.excepthook = erreur_final

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
        try:
            p.dowload_installer(proxy=proxy)
        except BaseException as b:
            # si il y a un probleme pendant le telechargement
            # on l'écrit et on passe au suivant
            sys.stdout.write('\r%s: %s   ' % (download_name, str(b)))
            sys.stdout.flush()
            print()

    print(Fore.LIGHTMAGENTA_EX + "Téléchargements terminés" + Fore.RESET)
    call_cmd("pause")
    return

if __name__ == '__main__':
    main()
