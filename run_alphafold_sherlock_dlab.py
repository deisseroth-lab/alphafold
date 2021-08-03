import logging
import os
import subprocess

from absl import app
from absl import flags
from absl import logging
import fasteners


LOCK_TIMEOUT = 3600 * 2  # 2 hours


class RunAlphaFoldDLabError(Exception):
    pass


flags.DEFINE_string('max_template_date', None, 'Maximum template release date '
                    'to consider (ISO-8601 format - i.e. YYYY-MM-DD). '
                    'Important if folding historical test sets.')
flags.DEFINE_enum('preset', 'full_dbs',
                  ['reduced_dbs', 'full_dbs', 'casp14'],
                  'Choose preset model configuration - no ensembling and '
                  'smaller genetic database config (reduced_dbs), no '
                  'ensembling and full genetic database config  (full_dbs) or '
                  'full genetic database config and 8 model ensemblings '
                  '(casp14).')
flags.DEFINE_string('input_path', None, 'Path to FASTA files')
flags.DEFINE_list('fasta_names', None, 'Names (w/o fasta extension) of FASTA files to process')
flags.DEFINE_string('output_path', None, 'Where to put the output')

FLAGS = flags.FLAGS

def main(argv):
    if len(argv) > 1:
        raise app.UsageError('Too many command-line arguments.')
    
    logging.info('Command line flags\n' +FLAGS.flags_into_string())    
    
    # TODO: Make data_dir and ssd_data_dir flags.
    group_scratch = os.environ['GROUP_SCRATCH']
    ssd_scratch = os.environ['L_SCRATCH']
    data_dir = os.path.join(group_scratch, "projects", "alphafold", "model_data")
    ssd_data_dir = os.path.join(ssd_scratch, "model_data")
    
    fasta_paths = ','.join([os.path.join(FLAGS.input_path, f"{f}.fasta") for f in FLAGS.fasta_names])

    # TODO: Make version_dir a flag.
    version_dir = os.environ['SINGULARITY_NAME'].strip(".sif")

    output_subdir = f"max_template_date_{FLAGS.max_template_date}__preset_{FLAGS.preset}"
    output_path = os.path.join(FLAGS.output_path, version_dir, output_subdir)

    run_env = os.environ.copy()
    run_env.update({
        "NVIDIA_VISIBLE_DEVICES": "all",
        "TF_FORCE_UNIFIED_MEMORY": "1",
        "XLA_PYTHON_CLIENT_MEM_FRACTION": "4.0",
    })

    dir_path = os.path.dirname(os.path.realpath(__file__))
    script = os.path.join(dir_path, "run_alphafold.py")

    run_command = [
        "python", script,
        "--fasta_paths", fasta_paths,
        "--output_dir", output_path,
        "--model_names", "model_1,model_2,model_3,model_4,model_5",
        "--data_dir", data_dir,
        "--uniref90_database_path", os.path.join(data_dir, "uniref90", "uniref90.fasta"),
        "--mgnify_database_path", os.path.join(data_dir, "mgnify", "mgy_clusters_2018_12.fa"),
        "--pdb70_database_path", os.path.join(data_dir, "pdb70", "pdb70"),
        "--template_mmcif_dir", os.path.join(data_dir, "pdb_mmcif", "mmcif_files"),
        "--obsolete_pdbs_path", os.path.join(data_dir, "pdb_mmcif", "obsolete.dat"),
        "--max_template_date", FLAGS.max_template_date,
        "--preset", FLAGS.preset,
        "--log_dir", output_path,
        "--logtostderr",
    ]

    db_list = []

    if FLAGS.preset == "reduced_dbs":
        run_command.extend([
            "--small_bfd_database_path",
            os.path.join(data_dir, "small_bfd", "bfd-first_non_consensus_sequences.fasta")
        ])
    else:
        db_list.extend([['bfd', 'uniclust30']])
        run_command.extend([
            "--bfd_database_path",
            os.path.join(ssd_data_dir, "bfd", "bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt"),
            "--uniclust30_database_path",
            os.path.join(ssd_data_dir, "uniclust30", "uniclust30_2018_08", "uniclust30_2018_08")
        ])

    if db_list:
        db2ssd(db_list, data_dir, ssd_data_dir)

    logging.info("Command: %s", run_command)
    subprocess.run(run_command, env=run_env, check=True)


def db2ssd(db_list, data_dir, ssd_data_dir):    
    for db in db_list:
        db_dir = os.path.join(data_dir, db)
        ssd_db_dir = os.path.join(ssd_data_dir, db)

        db_lockfile = db_dir + ".lock"
        lock = fasteners.InterProcessLock(db_lockfile)
        logging.info("About to wait for lockfile for %d sec: %s" % (LOCK_TIMEOUT, db_lockfile))
        gotten = lock.acquire(timeout=LOCK_TIMEOUT)
        if not gotten:
            raise RunAlphaFoldDLabError("Could not acquire lockfile for db copy")
        logging.info("Successfully acquired lockfile.")
 
        if os.exists(ssd_db_dir):
            logging.info("db already exists: %s", db)
            continue
        
        cmd = ["rclone", "copy", db_dir, ssd_db_dir]
        logging.info("Cloning db with command: %s", cmd)
        subprocess.run(cmd, check=True)
        lock.release()


if __name__ == '__main__':
    app.run(main)