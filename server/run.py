import os
import sys
import requests
import configparser
import numpy as np
import pandas as pd


def startOperation(remoteServer, useSlurm):
    testURL = 'https://rcdata.nau.edu/genomic-ml/PeakSegFPOP/labels/H3K4me3_TDH_ENCODE/samples/aorta/ENCFF115HTK/coverage.bigWig'
    problemsLocation = 'commands/genomes/hg19/problems.bed'

    problems = pd.read_csv(problemsLocation, sep='\t')
    problems.columns = ['chrom', 'problemStart', 'problemEnd']

    outputPath = 'test/'
    modelPath = 'commands/GenerateModel.R'

    if not os.path.exists(outputPath):
        try:
            os.makedirs(outputPath)
        except OSError:
            return

    def startBenchmark(args):
        chrom = args['chrom']
        start = args['problemStart']
        end = args['problemEnd']

        commandArgs = '%s %s %s %s %s %s' % (modelPath, testURL, outputPath, chrom, start, end)

        command = 'Rscript'

        if useSlurm:
            command = 'srun %s' % command

        os.system('%s %s' % (command, commandArgs))

    problems.apply(startBenchmark, axis=1)


def main():
    configFile = 'PeakLearnerSlurm.cfg'

    config = configparser.ConfigParser()
    config.read(configFile)

    configSections = config.sections()

    save = False

    # Setup a default config if doesn't exist
    if 'remoteServer' not in configSections:
        config.add_section('remoteServer')
        config.add_section('slurm')
        config['remoteServer']['url'] = '127.0.0.1:5000'
        config['slurm']['useSlurm'] = 'true'

        save = True

    # If a section was missing, save that to the config
    if save:
        with open(configFile, 'w') as cfg:
            config.write(cfg)

    peakLearnerWebServer = config['remoteServer']['url']
    useSlurm = config['slurm']['useSlurm'] == 'true'

    startOperation(peakLearnerWebServer, useSlurm)


if __name__ == '__main__':
    main()
