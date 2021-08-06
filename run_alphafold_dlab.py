"""Script to run alphafold the D-Lab way, using optional local SSD."""
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
flags.DEFINE_list('fasta_paths', None, 'Paths to FASTA files, each containing '
                  'one sequence. Paths should be separated by commas. '
                  'All FASTA paths must have a unique basename as the '
                  'basename is used to name the output directories for '
                  'each prediction.')
flags.DEFINE_string('output_dir', None, 'Path to a directory that will '
                    'store the results.')
flags.DEFINE_string('data_dir', None, 'Path to directory of supporting data.')
flags.DEFINE_string('ssd_data_dir', None, 'Local scratch space for fasta I/O.')

FLAGS = flags.FLAGS

def main(argv):
    if len(argv) > 1:
        raise app.UsageError('Too many command-line arguments.')
    
    logging.info('Command line flags\n' +FLAGS.flags_into_string())    
    
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
        "--fasta_paths", ','.join(FLAGS.fasta_paths),
        "--output_dir", FLAGS.output_dir,
        "--model_names", "model_1,model_2,model_3,model_4,model_5",
        "--data_dir", FLAGS.data_dir,
        "--uniref90_database_path", os.path.join(FLAGS.data_dir, "uniref90", "uniref90.fasta"),
        "--mgnify_database_path", os.path.join(FLAGS.data_dir, "mgnify", "mgy_clusters_2018_12.fa"),
        "--pdb70_database_path", os.path.join(FLAGS.data_dir, "pdb70", "pdb70"),
        "--template_mmcif_dir", os.path.join(FLAGS.data_dir, "pdb_mmcif", "mmcif_files"),
        "--obsolete_pdbs_path", os.path.join(FLAGS.data_dir, "pdb_mmcif", "obsolete.dat"),
        "--max_template_date", FLAGS.max_template_date,
        "--preset", FLAGS.preset,
        "--log_dir", FLAGS.log_dir,
        "--logtostderr",
    ]

    if FLAGS.preset == "reduced_dbs":
        run_command.extend([
            "--small_bfd_database_path",
            os.path.join(FLAGS.data_dir, "small_bfd", "bfd-first_non_consensus_sequences.fasta")
        ])
    else:
        if FLAGS.ssd_data_dir:
            os.makedirs(FLAGS.ssd_data_dir, exist_ok=True)
            for db in ['bfd', 'uniclust30']:
                safe_rclone(os.path.join(FLAGS.data_dir, db), os.path.join(FLAGS.ssd_data_dir, db))
            io_data_dir = FLAGS.ssd_data_dir
        else:
            io_data_dir = FLAGS.data_dir
        run_command.extend([
            "--bfd_database_path",
            os.path.join(io_data_dir, "bfd", "bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt"),
            "--uniclust30_database_path",
            os.path.join(io_data_dir, "uniclust30", "uniclust30_2018_08", "uniclust30_2018_08")
        ])

    logging.info("Command: %s", run_command)
    subprocess.run(run_command, env=run_env, check=True)


def safe_rclone(db_dir, ssd_db_dir):
    db_lockfile = ssd_db_dir + ".lock"
    lock = fasteners.InterProcessLock(db_lockfile)
    logging.info("Waiting for lockfile for %d sec: %s" % (LOCK_TIMEOUT, db_lockfile))
    gotten = lock.acquire(timeout=LOCK_TIMEOUT)
    if not gotten:
        raise RunAlphaFoldDLabError("Could not acquire lockfile")
    logging.info("Successfully acquired lockfile.")

    if os.path.exists(ssd_db_dir):
        logging.info("directory already exists: %s", ssd_db_dir)
    else:
        cmd = ["rclone", "copy", "--copy-links", db_dir, ssd_db_dir]
        logging.info("Cloning db with command: %s", cmd)
        subprocess.run(cmd, check=True)
    lock.release()


if __name__ == '__main__':
    app.run(main)