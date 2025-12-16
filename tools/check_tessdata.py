import os

def find_jpn():
    paths = []
    tp = os.getenv('TESSDATA_PREFIX')
    if tp:
        paths.append(tp)
    paths += [r'C:\Program Files\Tesseract-OCR\tessdata', r'C:\Program Files (x86)\Tesseract-OCR\tessdata']
    found = False
    for p in paths:
        pfile = os.path.join(p, 'jpn.traineddata')
        if os.path.exists(pfile):
            print('FOUND:' + pfile)
            found = True
    if not found:
        print('MISSING')

if __name__ == '__main__':
    find_jpn()
