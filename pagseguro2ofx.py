import datetime
from decimal import Decimal
from xml.etree import ElementTree
import sys

class Transaction(object):
    def __init__(self):
        self.id = None
        self.desc = None
        self.value = None
        self.date = None
        self.type = None # CREDIT or DEBIT

OFX_HEADER = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE
<OFX>
<SIGNONMSGSRSV1>
        <SONRS>
                <STATUS>
                        <CODE>0</CODE>
                        <SEVERITY>INFO</SEVERITY>
                </STATUS>
                <DTSERVER>%(start)s
                <LANGUAGE>%(language)s
                <DTACCTUP>%(start)s
                <FI>
                        <ORG>%(org)s
                        <FID>%(fid)s
                </FI>
        </SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
        <STMTTRNRS>
                <TRNUID>0
                <STATUS>
                        <CODE>0
                        <SEVERITY>INFO
                </STATUS>
                <STMTRS>
                        <CURDEF>BRL
                        <BANKACCTFROM>
                                <BANKID>001
                                <ACCTID>%(account)s
                                <ACCTTYPE>CHECKING
                        </BANKACCTFROM>
                        <BANKTRANLIST>
"""

OFX_STATEMENT = """
                                <STMTTRN>
                                        <TRNTYPE>%(type)s
                                        <DTPOSTED>%(date)s
                                        <TRNAMT>%(value)s
                                        <FITID>%(fid)s
                                        <CHECKNUM>%(checknum)s
                                        <MEMO>%(memo)s
                                </STMTTRN>
"""
OFX_FOOTER = """
                        </BANKTRANLIST>
                        <LEDGERBAL>
                                <BALAMT>%(balance)s
                                <DTASOF>%(end)s
                        </LEDGERBAL>
                </STMTRS>
        </STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""

class OFXWriter(object):
    def __init__(self, account):
        self.account = account
        self.transactions = []
        self.balance = Decimal(0)
        self.start = '20100201'
        self.end = '20100228'

    def add(self, transaction):
        self.transactions.append(transaction)

    def write(self, filename):
        fp = open(filename, 'w')
        self._write_header(fp)
        for transaction in self.transactions:
            self._write_transaction(fp, transaction)
        self._write_footer(fp)
        fp.close()

    def _format_date(self, dt):
        return dt.strftime('%Y%m%d')

    def _write_header(self, fp):
        fp.write(OFX_HEADER % dict(org='Pagseguro',
                                   fid='001',
                                   language='POR',
                                   start=self.start,
                                   account=self.account))

    def _write_transaction(self, fp, transaction):
        fp.write(OFX_STATEMENT % dict(type=transaction.type,
                                      date=self._format_date(transaction.date),
                                      value=transaction.value,
                                      fid=transaction.id,
                                      checknum=transaction.id,
                                      memo=transaction.desc.encode('latin1')))

    def _write_footer(self, fp):
        fp.write(OFX_FOOTER % dict(balance=self.balance,
                                   end=self.end))


class PagseguroParser(object):
    def __init__(self):
        self.transactions = []

    def read(self, filename):
        fp = open(filename)
        et = ElementTree.parse(fp)
        root = et.getroot()
        for node in root.findall('Table'):
            self._read_table(node)

    def _parse_value(self, text):
        text = text.replace('.', '')
        text = text.replace(',', '.')
        return Decimal(text)

    def _parse_date(self, text):
        return datetime.datetime.strptime(text, '%d/%m/%Y %H:%M:%S')

    def _read_table(self, node):
        status = node.find('Status').text
        if status != 'Aprovada':
            return
        date = self._parse_date(node.find('Data_Compensacao').text)
        t = Transaction()
        t.id = node.find('Transacao_ID').text.split('-')[0]
        t.value = self._parse_value(node.find('Valor_Bruto').text)
        t.desc = '%s (%s)' % (node.find('Cliente_Nome').text,
                              node.find('Cliente_Email').text)
        t.date = date
        self.transactions.append(t)

        if node.find('Debito_Credito').text == u'D\xe9bito':
            t.type = 'DEBIT'
            t.value = -t.value
        else:
            t.type = 'CREDIT'
        taxa = self._parse_value(node.find('Valor_Taxa').text)
        if taxa > 0:
            oldid = t.id
            t = Transaction()
            t.id = oldid
            t.type = 'CREDIT'
            t.desc = "Pagseguro taxa 3.99% + R$0.40"
            t.value = -self._parse_value(node.find('Valor_Taxa').text)
            t.date = date
            self.transactions.append(t)

def main():
    psp = PagseguroParser()
    psp.read(sys.argv[1])

    ow = OFXWriter('pagseguro@async.com.br')
    for transaction in psp.transactions:
        ow.add(transaction)
    ow.write(sys.argv[2])

if __name__ == '__main__':
    main()
