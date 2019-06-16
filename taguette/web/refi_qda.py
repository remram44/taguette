import uuid
from xml.sax.xmlreader import AttributesNSImpl

from .. import __version__


TAGUETTE_NAMESPACE = uuid.UUID('51B2B2B7-27EB-4ECB-9D56-E75B0A0496C2')


def write_codebook(tags, output):
    output.startElementNS(
        (None, 'CodeBook'), 'CodeBook',
        AttributesNSImpl({(None, 'origin'): 'Taguette %s' % __version__},
                         {(None, 'origin'): 'origin'}),
    )
    output.startElementNS(
        (None, 'Codes'), 'Codes',
        AttributesNSImpl({}, {}),
    )
    for tag in tags:
        guid = uuid.uuid5(TAGUETTE_NAMESPACE, tag.path)
        guid = str(guid).upper()
        output.startElementNS(
            (None, 'Code'), 'Code',
            AttributesNSImpl({(None, 'guid'): guid,
                              (None, 'name'): tag.path,
                              (None, 'isCodable'): 'true'},
                             {(None, 'guid'): 'guid',
                              (None, 'name'): 'name',
                              (None, 'isCodable'): 'isCodable'}),
        )
        output.endElementNS((None, 'Code'), 'Code')
    output.endElementNS((None, 'Codes'), 'Codes')
    output.startElementNS(
        (None, 'Sets'), 'Sets',
        AttributesNSImpl({}, {}),
    )
    output.endElementNS((None, 'Sets'), 'Sets')
    output.endElementNS((None, 'CodeBook'), 'CodeBook')


def write_project(project, output):
    output.startElementNS(
        (None, 'Project'), 'Project',
        AttributesNSImpl({(None, 'origin'): 'Taguette %s' % __version__,
                          (None, 'name'): project.name,
                          (None, 'creatingUserGUID'): '',
                          (None, 'creationDateTime'): '',
                          (None, 'modifiedDateTime'): ''},
                         {}),
    )
    output.startElementNS((None, 'Description'), 'Description',
                          AttributesNSImpl({}, {}))
    output.characters(project.description)
    output.endElementNS((None, 'Description'), 'Description')
    # Sources (TextSource)
    # Coding
    output.endElementNS((None, 'Project'), 'Project')
