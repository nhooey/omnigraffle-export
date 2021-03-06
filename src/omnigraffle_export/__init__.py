#!/usr/bin/env python

import os
import sys
import optparse
import logging
import tempfile
import hashlib

from Foundation import NSURL, NSMutableDictionary
from Quartz import PDFKit

from appscript import *

class OmniGraffleSchema(object):
    """ A class that encapsulates an OmniGraffle schema file"""

    # supported formarts
    EXPORT_FORMATS = {
        "eps": "EPS Format",
        "pdf": "Apple PDF pasteboard type",
        "png": "PNG",
        "svg": "Scalable Vector Graphics XML File Type",
    }

    # attribute header in PDF document that contains the checksum
    PDF_CHECKSUM_ATTRIBUTE = 'OmnigraffleExportChecksum: '

    def __init__(self, options, schemafile):
        schemafile = os.path.abspath(schemafile)  
        if not os.path.isfile(schemafile):
            raise ValueError('File: %s does not exists' % schemafile)

        self.options = options
        self.schemafile = os.path.abspath(schemafile)
        self.og = app('OmniGraffle Professional 5.app')
        self.og.activate()
        self.og.current_export_settings.area_type.set(k.all_graphics)
        self.doc = self.og.open(self.schemafile)

        logging.debug('Opened OmniGraffle file: ' + self.schemafile)

    def get_canvas_list(self):
        """
        Returns a list of names of all the canvases in the document
        """

        return [c.name() for c in self.doc.canvases()]

    def export(self, canvasname, file, format='pdf', force=False, is_checksum=False):
        """
        Exports one canvas named {@code canvasname}
        """

        format = format.lower()

        chksum = None
        if os.path.isfile(file) and not force:
            existing_chksum = checksum(file) if format != 'pdf' \
                                             else checksum_pdf(file)
            new_chksum = self.compute_canvas_checksum(canvasname)

            if existing_chksum == new_chksum and existing_chksum != None:
                logging.debug('No exporting - canvas %s not changed' % 
                              canvasname)
                return False
            else:
                chksum = new_chksum

        elif format == 'pdf':
            chksum = self.compute_canvas_checksum(canvasname)

        win = self.og.windows.first()

        canvas = [c for c in self.doc.canvases() if c.name() == canvasname]
        if len(canvas) == 1:
            canvas = canvas[0]
        else:
            logging.warn('Canvas %s does not exist in %s' % 
                         (canvasname, self.schemafile))
            return False

        self.og.set(win.canvas, to=canvas)

        export_format = OmniGraffleSchema.EXPORT_FORMATS[format]
        if (export_format == None):
            self.doc.save(in_=file)
        else:
            self.doc.save(as_=export_format, in_=file)

        if not is_checksum and self.options.verbose:
            print "%s" % file

        logging.debug("Exported `%s' into `%s' as %s" % (canvasname, file, format))

        if format == 'pdf':
            # save the checksum
            url = NSURL.fileURLWithPath_(file)
            pdfdoc = PDFKit.PDFDocument.alloc().initWithURL_(url)
            attrs = NSMutableDictionary.alloc().initWithDictionary_(pdfdoc.documentAttributes())

            attrs[PDFKit.PDFDocumentSubjectAttribute] = \
                '%s%s' % (OmniGraffleSchema.PDF_CHECKSUM_ATTRIBUTE, chksum)

            pdfdoc.setDocumentAttributes_(attrs)
            pdfdoc.writeToFile_(file)

        return True

    def export_all(self, targetdir, fmt='pdf', force=False,
                  namemap=lambda c, f: "%s.%s" % (c, f)):
        """
        Exports all canvases
        """

        for c in self.get_canvas_list():
            targetfile = os.path.join(os.path.abspath(targetdir), namemap(c, fmt))
            logging.debug("Exporting `%s' into `%s' as %s" % 
                          (c, targetfile, fmt))
            self.export(c, targetfile, fmt, force)

    def compute_canvas_checksum(self, canvasname):
        tmpfile = tempfile.mkstemp(suffix='.png')[1]
        os.unlink(tmpfile)

        assert self.export(canvasname, tmpfile, 'png', True, True)

        try:
            chksum = checksum(tmpfile)
            return chksum
        finally:
            os.unlink(tmpfile)


def checksum(filepath):
    assert os.path.isfile(filepath), '%s is not a file' % filepath

    c = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(128), ''):
            c.update(chunk)
    
    return c.hexdigest()

def checksum_pdf(filepath):
    assert os.path.isfile(filepath), '%s is not a file' % filepath

    url = NSURL.fileURLWithPath_(filepath)
    pdfdoc = PDFKit.PDFDocument.alloc().initWithURL_(url)
    assert pdfdoc != None
    chksum = pdfdoc.documentAttributes()[PDFKit.PDFDocumentSubjectAttribute]

    if not chksum.startswith(OmniGraffleSchema.PDF_CHECKSUM_ATTRIBUTE):
        return None
    else:
        return chksum[len(OmniGraffleSchema.PDF_CHECKSUM_ATTRIBUTE):]

def main():
    usage = "usage: %prog [options] <source> <target>"
    parser = optparse.OptionParser(usage=usage)

    parser.add_option('-f', 
                      help='format (one of: pdf, png, svg, eps), default pdf',
                      metavar='FMT', dest='format', default='pdf')
    parser.add_option('--force', action='store_true', help='force the export', 
                      dest='force')
    parser.add_option('-v', action='store_true', help='verbose', dest='verbose')
    parser.add_option('--verbose', action='store_true', help='verbose', dest='verbose')
    parser.add_option('-d', action='store_true', help='debug', dest='debug')
    parser.add_option('--debug', action='store_true', help='debug', dest='debug')
    parser.add_option('-c', 
                      help='canvas name (if not given -t must point to a directory)', 
                      metavar='NAME', dest='canvas')

    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        sys.exit(1)

    source, target = args

    if not options.canvas and not os.path.isdir(target):
        print >> sys.stderr, "Without canvas name, the target (-t) must be a directory"
        sys.exit(1)

    if options.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')

    schema = OmniGraffleSchema(options, source)

    if options.canvas:
        schema.export(options.canvas, target, options.format,
                      force=options.force)
    else:
        schema.export_all(target, fmt=options.format, force=options.force)

if __name__ == '__main__':
    main()

