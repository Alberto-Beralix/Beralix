# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2008-2009 Yu Yuwei <acevery@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# $Id: $
#
import sys
reload (sys)
sys.setdefaultencoding('utf-8')

tab_dict = {
    '0':0,
    'a':1, 'b':2, 'c':3, 'd':4, 'e':5, 
    'f':6, 'g':7, 'h':8, 'i':9, 'j':10,
    'k':11, 'l':12, 'm':13, 'n':14, 'o':15,
    'p':16, 'q':17, 'r':18, 's':19, 't':20,
    'u':21, 'v':22, 'w':23, 'x':24, 'y':25,
    'z':26, "'":27, ';':28, '`':29, '~':30, 
    '!':31, '@':32, '#':33, '$':34, '%':35,
    '^':36, '&':37, '*':38, '(':39, ')':40,
    '-':41, '_':42, '=':43, '+':44, '[':45,
    ']':46, '{':47, '}':48, '|':49, '/':50,
    ':':51, '"':52,  '<':53, '>':54, ',':55,
    '.':56, '?':57, '\\':58, 'A':59, 'B':60,
    'C':61, 'D':62, 'E':63, 'F':64, 'G':65,
    'H':66, 'I':67, 'J':68, 'K':69, 'L':70,
    'M':71, 'N':72, 'O':73, 'P':74, 'Q':75,
    'R':76, 'S':77, 'T':78, 'U':79, 'V':80,
    'W':81, 'X':82, 'Y':83, 'Z':84, '0':85,
    '1':86, '2':87, '3':88, '4':89, '5':90,
    '6':91, '7':92, '8':93, '9':94
    }

tab_key_list = tab_dict.keys()

id_tab_dict = {}
for key,id in tab_dict.items():
    id_tab_dict[id] = key

class tab_key(object):
    '''The class store'''
    def __init__(self, xm_key):
        self._key = xm_key
        try:
            self._key_id = tab_dict[xm_key]
        except KeyError, e:
            # give a false value
            self._key_id = -1
            error_m = u'%s is not in tab_dict' % xm_key
            print error_m.encode('utf8')
            import traceback
            traceback.print_exc ()
    
    def get_key_id(self):
        return self._key_id

    def get_key(self):
        return self._key

    def __str__(self):
        return self._key

    def __int__(self):
        return self._key_id

def parse ( inputstr ):
    
    ids_input = []
    try:
        ids_input = map (tab_key,inputstr)
    except:
        pass
    return ids_input[:]

def deparse (id):
    '''deparse the id code of tables, id could be int or int in string form'''
    if id:
        id = int(id)
        if id in id_tab_dict:
            return id_tab_dict[id]
    else:
        return ''

chinese_nc_chars="“”‘’《》〈〉〔〕「」『』【】〖〗（）［］｛｝"\
    "．。，、；：？！…—·ˉˇ¨々～‖∶＂＇｀｜"\
    "⒈⒉⒊⒋⒌⒍⒎⒏⒐⒑⒒⒓⒔⒕⒖⒗⒘⒙⒚⒛"\
    "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯЁ"\
    "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"\
    "⒈⒉⒊⒋⒌⒍⒎⒏⒐⒑⒒⒓⒔⒕⒖⒗⒘⒙⒚⒛"\
    "㎎㎏㎜㎝㎞㎡㏄㏎㏑㏒㏕"\
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"\
    "⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿⒀⒁⒂⒃⒄⒅⒆⒇"\
    "€＄￠￡￥"\
    "¤→↑←↓↖↗↘↙"\
    "ァアィイゥウェエォオカガキギクグケゲコゴサザシジ"\
    "スズセゼソゾタダチヂッツヅテデトドナニヌネノハバパ"\
    "ヒビピフブプヘベペホボポマミムメモャヤュユョヨラ"\
    "リルレロヮワヰヱヲンヴヵヶーヽヾ"\
    "ぁあぃいぅうぇえぉおかがきぎぱくぐけげこごさざしじ"\
    "すずせぜそぞただちぢっつづてでとどなにぬねのはば"\
    "ひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらり"\
    "るれろゎわゐゑをん゛゜ゝゞ"\
    "勹灬冫艹屮辶刂匚阝廾丨虍彐卩钅冂冖宀疒肀丿攵凵犭"\
    "亻彡饣礻扌氵纟亠囗忄讠衤廴尢夂丶"\
    "āáǎàōóǒòêēéěèīíǐìǖǘǚǜüūúǔù"\
    "＋－＜＝＞±×÷∈∏∑∕√∝∞∟∠∣∥∧∨∩∪∫∮"\
    "∴∵∶∷∽≈≌≒≠≡≤≥≦≧≮≯⊕⊙⊥⊿℃°‰"\
    "♂♀§№☆★○●◎◇◆□■△▲※〓＃＆＠＼＾＿￣"\
    "абвгдежзийклмнопрстуфхцчшщъыьэюяё"\
    "ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹβγδεζηαικλμνξοπρστυφθψω"\
    "①②③④⑤⑥⑦⑧⑨⑩①②③④⑤⑥⑦⑧⑨⑩"\
    "㈠㈡㈢㈣㈤㈥㈦㈧㈨㈩㈠㈡㈢㈣㈤㈥㈦㈧㈨㈩"\
    "ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙㄧㄨㄩ"\
    "ㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦ"
chinese_nocheck_chars = chinese_nc_chars.decode('utf8')
