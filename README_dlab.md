# AlphaFold on Sherlock

The [`dlab-sherlock`](https://github.com/deisseroth-lab/alphafold/tree/dlab-sherlock) branch contains minor updates to the AlphaFold pipeline, as well as scripts to make AF usable in the D-Lab's Sherlock cluster.

## Quick Start

If you are itching to get predicting on your FASTA files and are familiar with the
3 main AlphaFold flags (`max_template_date`, `preset`, and `fasta_paths`), the following
command demonstrates how to quickly get started.  For details on these flags see the
[AF docs](https://github.com/deepmind/alphafold/blob/main/README.md#running-alphafold)  

From within your clone of the alphafold repo on Sherlock:

```sh
git checkout dlab-sherlock
python3 run_alphafold_dlab_slurm.py \
    --output_dir $OAK/users/$USER/alphafold/output \
    --max_template_date 2100-01-01 \
    --preset full_dbs \
    --fasta_paths=$OAK/users/$USER/alphafold/fasta/protein0.fasta,$OAK/users/$USER/alphafold/fasta/protein1.fasta \
    --job_name twoproteins \
```

The output will be stored in a directory denoting the D-Lab alphafold software version used, and the
flags used.  For the command above, this would be:

```sh
<output_dir>/alphafold_2021.8.0__max_template_date_2100-01-01__preset_full_dbs/twoproteins
```

Within that directory there will be:

- A subdirectory for each fasta file containing the AlphaFold prediction information the protein sequence.
- The script, named `<job_name>.sbatch`, which was submitted to the Sherlock SLURM scheduler.
- A logs subdirectory containing any output logs from the job.  Currently this a single file with the 
  SLURM job's stdout and stderr.

## Changes for SLURM

The more pertinent changes to run AF on Sherlock:

- Update Dockerfile to use `HAVE_AVX2=1` compile flag, so that it will run on AMD CPUs within the cluster,
  even if built on an Intel CPU with additional functionality.  This turns off AVX512.  
  The Dockerfile also adds the [rclone](https://rclone.org/) utility for fast data copies.
- Build rules for a Singularity image (via a Docker image).  There is a [Makefile](Makefile) to aid in this process,
  which builds the image in the `/tmp/alphafold` directory.
- Add [run_alphafold_dlab.py](run_alphafold_dlab.py) to unify input data paths and
  optionally copy high IOPS databases to local SSD before starting predictions.  Under the hood, this script
  uses [run_alphafold.py](run_alphafold.py), which has been slightly updated for easier configurability.
  Advanced users can run this interactively on a node, if desired.
- Add [run_alphafold_dlab_slurm.py](run_alphafold_dlab_slurm.py) (a python3.6 compatible script with no
  dependencies) to launch a SLURM job that will execute [run_alphafold_dlab.py](run_alphafold_dlab.py) 
  using the default Singularity container.  This is the main driver script most users will use.

## Building new Singularity image

To create a new version, once must use a non-Sherlock machine.   This is because Sherlock does not give root
access, which is needed to build intermediate Docker images.  To release a new software version: tag the 
repo with the version, run make, and then copy the output to our group space.  Versioning uses the
[CalVer](https://calver.org/) YYYY.MM.MICRO syntax: year, month, and monthly release number.  

Example release, on a non-Sherlock machine:

```sh
git tag 2021.8.0
make
scp /tmp/alphafold/alphafold_2021.8.0.sif sherlock:/home/groups/deissero/projects/alphafold/singularity
```

To make the new version the default, update the symlink on a Sherlock machine:

```sh
cd $GROUP_HOME/projects/alphafold/singularity/
ln -sf alphafold_2021.8.0.sif alphafold.sif
```
