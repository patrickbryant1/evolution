#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import sys
import os
import pexpect
import subprocess
import pdb

#Other script imports
from hh_reader import read_result

#FUNCTIONS
def pdb_to_fasta(uid, outdir):
	'''Convert pdb file to fasta.
	'''

	inname = uid+'.pdb'
	outname = uid+'.fa'
	#Path to pdb parser
	command = 'python /home/p/pbryant/pfs/evolution/CATH/parse_pdb_resid.py ' + inname
	outp = subprocess.check_output(command, shell = True)#Save AA sequence
	sequence = outp.split('\n')[0]
	pdb.set_trace()
	with open(outdir+outname, "w") as outfile:
		outfile.write('>'+uid+'\n')
		i = 0 #index
		while i<len(sequence):
			outfile.write(sequence[i:i+60]+'\n')
			i+=60

	return None

def run_hhblits(uid, outdir, hhblits, uniprot):
	'''A function that runs hhblits to create a HMM of an input sequence in fasta format
	'''


	inname = uid+'.fa'
	outname = uid+'.hhm'
	statement = hhblits +' -i ' +outdir+inname + ' -d ' + uniprot + ' -ohhm ' + outname
	outp = subprocess.check_output(statement, shell = True)
	
	return None

def seq_to_pdb(aligned_seq, start, end, uid):
	'''Extracts CAs from pdb file based on sequence.
	Enables extraction of residues in alignment for
	further use.
	'''

	pdb_file = uid + '.pdb'
	command = 'python /home/p/pbryant/pfs/evolution/CATH/parse_pdb_resid.py ' + pdb_file
        outp = subprocess.check_output(command, shell = True)#Save parsed pdb
	outp = outp.split('\n')
	original_seq = outp[0]
	ca_pdb = outp[1:-1] 
	pdb.set_trace()

