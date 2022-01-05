"""Script to launch an alphafold SLURM job the D-Lab way."""

import argparse
import logging
import os
import shlex
import subprocess


def main(fasta_paths, 
         is_prokaryote_list, 
         output_dir, 
         max_template_date, 
         db_preset, 
         model_preset,
         job_name, 
         partition, 
         time, 
         constraint,
         container_path, 
         data_dir, 
         ssd_data_dir,
         log_only):

    log_dir = os.path.join(output_dir, "logs")
    logging.info("Logging directory:\n%s", log_dir)

    slurm_output_path = os.path.join(log_dir, "slurm-%j.out")
    logging.info("SLURM output path (%%j=job_id):\n%s", slurm_output_path)

    # mem-per-cpu: Found that asking for 8GB on systems with 8GB per core may 
    #              "round up" and take 2x the requested cores.
    slurm_args = [
        "--job-name", job_name,
        "--time", time,
        "--partition", partition,
        "--constraint", constraint,
        "--cpus-per-task", "15",
        "--mem-per-cpu", "7GB",  
        "--gpus", "1",
        "--output", slurm_output_path,
    ]

    singularity_command = [
        "singularity", "run",
        "--nv", "--pwd", "/app/alphafold",
        container_path
    ]

    script_path = os.path.join(output_dir, f"{job_name}.sbatch")
    logging.info("Script path:\n%s", script_path)
    
    alphafold_dlab_args = [
        "--fasta_paths", fasta_paths,
        "--output_dir", output_dir,
        "--data_dir", data_dir,
        "--ssd_data_dir", ssd_data_dir,
        "--max_template_date", max_template_date,
        "--db_preset", db_preset,
        "--model_preset", model_preset,
        "--log_dir", log_dir,
    ]
    if is_prokaryote_list:
        alphafold_dlab_args.extend(["--is_prokaryote_list"], is_prokaryote_list)

    script_command = singularity_command + alphafold_dlab_args
    # shlex join requires python 3.8
    # script_command_quoted = shlex.join(script_command)
    script_command_quoted = ' '.join(shlex.quote(x) for x in script_command)
    logging.info("Script command:\n%s", script_command_quoted)

    slurm_command = ["sbatch"] + slurm_args + [script_path]
    logging.info("Slurm command list:\n%s", slurm_command)

    if log_only:
        return

    os.makedirs(full_output_dir, exist_ok=False)
    os.makedirs(log_dir)

    script_text = f"""#!/bin/bash
{script_command_quoted}
"""

    with open(script_path, "w") as f:
        f.write(script_text)

    subprocess.run(slurm_command, check=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Launch alphafold on SLURM")
    parser.add_argument("--fasta_paths", required=True,
                        help="Fasta files to process (basenames should be unique)")
    parser.add_argument("--is_prokaryote_list", 
                        help="If fasta files contain prokaryotes (only for multimer models)")
    parser.add_argument("--output_dir", required=True,
                        help="Directory within which to create subdirectories for output (one per fasta_path)")
    parser.add_argument("--max_template_date", required=True,
                        help="Maximum template release date to consider. Important if folding historical test sets.")
    parser.add_argument("--db_preset", required=True, choices=['reduced_dbs', 'full_dbs'],
                        help="Preset db configuration (see Alphafold docs)")
    parser.add_argument("--model_preset", required=True, choices=['monomer', 'monomer_casp14', 'monomer_ptm', 'multimer'],
                        help="Preset model configuration (see Alphafold docs)")

    parser.add_argument("--job_name", required=True, help="SLURM job_name")
    parser.add_argument("--partition", default="owners", help="SLURM partition")
    parser.add_argument("--time", default="48:00:00", help="Expected SLURM job time")
    # There is no constraint to use nodes with large SSD, so instead use the
    # RME cpu constraint.  RME cpus are on machines with large local SSD.
    parser.add_argument("--constraint", default="(GPU_SKU:A100_PCIE|GPU_SKU:A100_SXM4)&CPU_GEN:RME",
                        help="SLURM jobs constraint")
    parser.add_argument("--log_only", default=False, action="store_true",
                        help="Do not submit to slurm, only log commands. Useful for debugging.")

    args = parser.parse_args()

    # Locations specific to the D-Lab
    group_home = os.environ["GROUP_HOME"]
    group_scratch = os.environ['GROUP_SCRATCH']
    ssd_scratch = os.environ['L_SCRATCH']

    container_path = os.path.join(group_home, "projects", "alphafold", "singularity", "alphafold.sif")
    container_path = os.path.realpath(container_path)

    version = os.path.splitext(os.path.basename(container_path))[0]
    output_subdir = f"{version}__max_template_date_{args.max_template_date}__db_preset_{args.db_preset}__model_preset_{args.model_preset}"
    full_output_dir = os.path.join(args.output_dir, output_subdir, args.job_name)

    data_dir = os.path.join(group_scratch, "projects", "alphafold", "model_data")
    ssd_data_dir = os.path.join(ssd_scratch, "model_data")

    main(fasta_paths=args.fasta_paths, 
         is_prokaryote_list=args.is_prokaryote_list, 
         output_dir=full_output_dir, 
         max_template_date=args.max_template_date, 
         db_preset=args.db_preset, 
         model_preset=args.model_preset,
         job_name=args.job_name, 
         partition=args.partition, 
         time=args.time, 
         constraint=args.constraint,
         container_path=container_path, 
         data_dir=data_dir, 
         ssd_data_dir=ssd_data_dir, 
         log_only=args.log_only)
