"""
 @Author: jiran
 @Email: jiran214@qq.com
 @FileName: config.py
 @DateTime: 2023/4/7 14:30
 @SoftWare: PyCharm
"""
import configparser
from utils.path import get_absolute_file_path

config_filename = 'config.ini'

file_path = get_absolute_file_path(config_filename)
_config = configparser.RawConfigParser()
_config.read(file_path)

service_settings = dict(_config.items('service'))


api_key = _config.get('openai', 'api_key')
debug = _config.getboolean('other', 'debug')
proxy = _config.get('other', 'proxy')
cookie = _config.get('other', 'bili_cookie')

if __name__ == '__main__':
    print(service_settings, api_key, proxy)