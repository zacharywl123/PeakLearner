import pandas as pd
from core.util import PLdb as db
from core.Handlers import Models, Handler
from simpleBDB import retry, txnAbortOnError


labelColumns = ['chrom', 'chromStart', 'chromEnd', 'annotation']
jbrowseLabelColumns = ['ref', 'start', 'end', 'label']


def addLabel(data, txn=None):
    # Duplicated because calls from updateLabel are causing freezing
    perms = db.Permission(data['user'], data['hub']).get(txn=txn)
    if perms.hasPermission(data['currentUser'], 'Label'):
        newLabel = pd.Series({'chrom': data['ref'],
                              'chromStart': data['start'],
                              'chromEnd': data['end'],
                              'annotation': data['label'],
                              'createdBy': data['currentUser'],
                              'lastModifiedBy': data['currentUser']})
        labelsDb = db.Labels(data['user'], data['hub'], data['track'], data['ref'])
        labels = labelsDb.get(txn=txn, write=True)
        if not labels.empty:
            inBounds = labels.apply(db.checkInBounds, axis=1, args=(data['ref'], data['start'], data['end']))
            # If there are any labels currently stored within the region which the new label is being added
            if inBounds.any():
                raise db.AbortTXNException

        labels = labels.append(newLabel, ignore_index=True).sort_values('chromStart', ignore_index=True)

        labelsDb.put(labels, txn=txn)
        db.Prediction('changes').increment(txn=txn)
        Models.updateAllModelLabels(data, labels, txn)
    return data


@retry
@txnAbortOnError
def addHubLabels(data, txn=None):
    # Duplicated because calls from updateLabel are causing freezing
    perms = db.Permission(data['user'], data['hub']).get(txn=txn)
    if perms.hasPermission(data['currentUser'], 'Label'):
        newLabel = pd.Series({'chrom': data['ref'],
                              'chromStart': data['start'],
                              'chromEnd': data['end'],
                              'annotation': data['label'],
                              'createdBy': data['currentUser'],
                              'lastModifiedBy': data['currentUser']})

        if 'tracks' in data:
            tracks = data['tracks']
        else:
            hubInfo = db.HubInfo(data['user'], data['hub']).get(txn=txn)
            tracks = list(hubInfo['tracks'].keys())

        for track in tracks:
            data['track'] = track
            trackTxn = db.getTxn(parent=txn)
            labelsDb = db.Labels(data['user'], data['hub'], data['track'], data['ref'])
            labels = labelsDb.get(txn=trackTxn, write=True)
            if not labels.empty:
                inBounds = labels.apply(db.checkInBounds, axis=1, args=(data['ref'], data['start'], data['end']))
                # If there are any labels currently stored within the region which the new label is being added
                if inBounds.any():
                    trackTxn.abort()
                    raise db.AbortTXNException

            labels = labels.append(newLabel, ignore_index=True).sort_values('chromStart', ignore_index=True)

            labelsDb.put(labels, txn=trackTxn)
            db.Prediction('changes').increment(txn=trackTxn)
            Models.updateAllModelLabels(data, labels, trackTxn)
            trackTxn.commit()
    return data


# Removes label from label file
def deleteLabel(data, txn=None):
    perms = db.Permission(data['user'], data['hub']).get(txn=txn)
    if perms.hasPermission(data['currentUser'], 'Label'):
        toRemove = pd.Series({'chrom': data['ref'],
                              'chromStart': data['start'],
                              'chromEnd': data['end']})

        labels = db.Labels(data['user'], data['hub'], data['track'], data['ref'])
        removed, after = labels.remove(toRemove, txn=txn)
        db.Prediction('changes').increment(txn=txn)
        Models.updateAllModelLabels(data, after, txn)
    return removed.to_dict()


def deleteHubLabels(data, txn=None):
    perms = db.Permission(data['user'], data['hub']).get(txn=txn)
    if perms.hasPermission(data['currentUser'], 'Label'):
        labelToRemove = pd.Series({'chrom': data['ref'],
                                   'chromStart': data['start'],
                                   'chromEnd': data['end']})

        user = data['user']
        hub = data['hub']

        if 'tracks' in data:
            tracks = data['tracks']
        else:
            hubInfo = db.HubInfo(data['user'], data['hub']).get(txn=txn)
            tracks = list(hubInfo['tracks'].keys())

        for track in tracks:
            data['track'] = track
            trackTxn = db.getTxn(parent=txn)
            labelDb = db.Labels(user, hub, track, data['ref'])
            item, labels = labelDb.remove(labelToRemove, txn=trackTxn)
            db.Prediction('changes').increment(txn=trackTxn)
            Models.updateAllModelLabels(data, labels, trackTxn)
            trackTxn.commit()


def updateLabel(data, txn=None):
    perms = db.Permission(data['user'], data['hub']).get(txn=txn)
    if perms.hasPermission(data['currentUser'], 'Label'):
        label = data['label']

        labelToUpdate = pd.Series({'chrom': data['ref'],
                                   'chromStart': data['start'],
                                   'chromEnd': data['end'],
                                   'annotation': label,
                                   'lastModifiedBy': data['currentUser']})
        labelDb = db.Labels(data['user'], data['hub'], data['track'], data['ref'])
        db.Prediction('changes').increment(txn=txn)
        item, labels = labelDb.add(labelToUpdate, txn=txn)
        Models.updateAllModelLabels(data, labels, txn)


@retry
@txnAbortOnError
def updateHubLabels(data, txn=None):
    perms = db.Permission(data['user'], data['hub']).get(txn=txn)
    if perms.hasPermission(data['currentUser'], 'Label'):
        labelToUpdate = pd.Series({'chrom': data['ref'],
                                   'chromStart': data['start'],
                                   'chromEnd': data['end'],
                                   'annotation': data['label'],
                                   'lastModifiedBy': data['currentUser']})

        user = data['user']
        hub = data['hub']

        if 'tracks' in data:
            tracks = data['tracks']
        else:
            hubInfo = db.HubInfo(data['user'], data['hub']).get(txn=txn)
            tracks = list(hubInfo['tracks'].keys())

        for track in tracks:
            data['track'] = track
            trackTxn = db.getTxn(parent=txn)
            labelDb = db.Labels(user, hub, track, data['ref'])
            db.Prediction('changes').increment(txn=trackTxn)
            item, labels = labelDb.add(labelToUpdate, txn=trackTxn)
            Models.updateAllModelLabels(data, labels, trackTxn)
            trackTxn.commit()

        return item.to_dict()


@retry
@txnAbortOnError
def getLabels(data, txn=None):
    labels = db.Labels(data['user'], data['hub'], data['track'], data['ref'])
    labelsDf = labels.getInBounds(data['ref'], data['start'], data['end'], txn=txn)
    if len(labelsDf.index) < 1:
        return []

    labelsDf = labelsDf[labelColumns]
    labelsDf.columns = jbrowseLabelColumns

    return labelsDf


@retry
@txnAbortOnError
def getHubLabels(data, txn=None):
    if 'tracks' in data:
        tracks = data['tracks']
    else:
        hubInfo = db.HubInfo(data['user'], data['hub']).get(txn=txn)
        tracks = list(hubInfo['tracks'].keys())

    output = pd.DataFrame()

    for track in tracks:
        if 'ref' in data:
            labelsDb = db.Labels(data['user'], data['hub'], track, data['ref'])
            if 'start' in data and 'end' in data:
                labels = labelsDb.getInBounds(data['ref'], data['start'], data['end'], txn=txn)
            else:
                labels = labelsDb.get(txn=txn)
        else:
            availableRefs = db.Labels.keysWhichMatch(data['user'], data['hub'], track)

            labels = pd.DataFrame()

            for refKey in availableRefs:
                print(refKey)
                labels = labels.append(db.Labels(*refKey).get(txn=txn))

        labels['track'] = track

        output = output.append(labels)

    return output


def stats():
    chroms = labels = 0

    for key in db.Labels.db_key_tuples():
        labelsDf = db.Labels(*key).get()

        if labelsDf.empty:
            continue

        chroms = chroms + 1

        labels = labels + len(labelsDf.index)

    return chroms, labels
