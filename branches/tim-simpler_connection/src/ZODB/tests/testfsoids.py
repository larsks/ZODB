##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

r"""
fsoids test, of the workhorse fsoids.Trace class
================================================

Let's get a temp file path to work with first.

>>> import tempfile
>>> path = tempfile.mktemp('.fs', 'Data')
>>> print 'path:', path #doctest: +ELLIPSIS
path: ...Data...fs

More imports.

>>> import ZODB
>>> from ZODB.FileStorage import FileStorage
>>> import transaction as txn
>>> from BTrees.OOBTree import OOBTree
>>> from ZODB.FileStorage.fsoids import Tracer  # we're testing this

Create an empty FileStorage.

>>> st = FileStorage(path)

There's not a lot interesting in an empty DB!

>>> t = Tracer(path)
>>> t.register_oids(0x123456)
>>> t.register_oids(1)
>>> t.register_oids(0)
>>> t.run()
>>> t.report()
oid 0x00 <unknown> 0 revisions
    this oid was neither defined nor referenced
oid 0x01 <unknown> 0 revisions
    this oid was neither defined nor referenced
oid 0x123456 <unknown> 0 revisions
    this oid was neither defined nor referenced

That didn't tell us much, but does show that the specified oids are sorted
into increasing order.

Create a root object and try again:

>>> db = ZODB.DB(st) # yes, that creates a root object!
>>> t = Tracer(path)
>>> t.register_oids(0, 1)
>>> t.run(); t.report() #doctest: +ELLIPSIS
oid 0x00 persistent.mapping.PersistentMapping 1 revision
    tid 0x... offset=4 ...
        tid user=''
        tid description='initial database creation'
        new revision persistent.mapping.PersistentMapping at 52
oid 0x01 <unknown> 0 revisions
    this oid was neither defined nor referenced

So we see oid 0 has been used in our one transaction, and that it was created
there, and is a PersistentMapping.  4 is the file offset to the start of the
transaction record, and 52 is the file offset to the start of the data record
for oid 0 within this transaction.  Because tids are timestamps too, the
"..." parts vary across runs.  The initial line for a tid actually looks like
this:

    tid 0x035748597843b877 offset=4 2004-08-20 20:41:28.187000

Let's add a BTree and try again:

>>> root = db.open().root()
>>> root['tree'] = OOBTree()
>>> txn.get().note('added an OOBTree')
>>> txn.get().commit()
>>> t = Tracer(path)
>>> t.register_oids(0, 1)
>>> t.run(); t.report() #doctest: +ELLIPSIS
oid 0x00 persistent.mapping.PersistentMapping 2 revisions
    tid 0x... offset=4 ...
        tid user=''
        tid description='initial database creation'
        new revision persistent.mapping.PersistentMapping at 52
    tid 0x... offset=168 ...
        tid user=''
        tid description='added an OOBTree'
        new revision persistent.mapping.PersistentMapping at 207
        references 0x01 <unknown> at 207
oid 0x01 BTrees._OOBTree.OOBTree 1 revision
    tid 0x... offset=168 ...
        tid user=''
        tid description='added an OOBTree'
        new revision BTrees._OOBTree.OOBTree at 363
        referenced by 0x00 persistent.mapping.PersistentMapping at 207

So there are two revisions of oid 0 now, and the second references oid 1.
It's peculiar that the class shows as <unknown> in:

        references 0x01 <unknown> at 207

The code that does this takes long tours through undocumented code in
cPickle.c (using cPickle features that aren't in pickle.py, and aren't even
documented as existing).  Whatever the reason, ZODB/util.py's get_refs()
function returns (oid_0x01, None) for the reference to oid 1, instead of the
usual (oid, (module_name, class_name)) form.  Before I wrote this test,
I never saw a case of that before!  "references" lines usually identify
the class of the object.  Anyway, the correct class is given in the new
output for oid 1.

One more, storing a reference in the BTree back to the root object:

>>> tree = root['tree']
>>> tree['root'] = root
>>> txn.get().note('circling back to the root')
>>> txn.get().commit()
>>> t = Tracer(path)
>>> t.register_oids(*range(3))
>>> t.run(); t.report() #doctest: +ELLIPSIS
oid 0x00 persistent.mapping.PersistentMapping 2 revisions
    tid 0x... offset=4 ...
        tid user=''
        tid description='initial database creation'
        new revision persistent.mapping.PersistentMapping at 52
    tid 0x... offset=168 ...
        tid user=''
        tid description='added an OOBTree'
        new revision persistent.mapping.PersistentMapping at 207
        references 0x01 <unknown> at 207
    tid 0x... offset=443 ...
        tid user=''
        tid description='circling back to the root'
        referenced by 0x01 BTrees._OOBTree.OOBTree at 491
oid 0x01 BTrees._OOBTree.OOBTree 2 revisions
    tid 0x... offset=168 ...
        tid user=''
        tid description='added an OOBTree'
        new revision BTrees._OOBTree.OOBTree at 363
        referenced by 0x00 persistent.mapping.PersistentMapping at 207
    tid 0x... offset=443 ...
        tid user=''
        tid description='circling back to the root'
        new revision BTrees._OOBTree.OOBTree at 491
        references 0x00 <unknown> at 491
oid 0x02 <unknown> 0 revisions
    this oid was neither defined nor referenced

Note that we didn't create any new object there (oid 2 is still unused), we
just made oid 1 refer to oid 0.  Therefore there's a new "new revision" line
in the output for oid 1.  Note that there's also new output for oid 0, even
though the root object didn't change:  we got new output for oid 0 because
it's a traced oid and the new transaction made a new reference *to* it.

Since the Trace constructor takes only one argument, the only sane thing
you can do to make it fail is to give it a path to a file that doesn't
exist:

>>> Tracer('/eiruowieuu/lsijflfjlsijflsdf/eurowiurowioeuri/908479287.fs')
Traceback (most recent call last):
  ...
ValueError: must specify an existing FileStorage

You get the same kind of exception if you pass it a path to an existing
directory (the path must be to a file, not a directory):

>>> import os
>>> Tracer(os.path.dirname(__file__))
Traceback (most recent call last):
  ...
ValueError: must specify an existing FileStorage


Clean up.
>>> st.close()
>>> st.cleanup() # remove .fs, .index, etc
"""

from zope.testing import doctest

def test_suite():
    return doctest.DocTestSuite()
