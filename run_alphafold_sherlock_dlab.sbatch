#!/bin/bash
#
#SBATCH --job-name=alphafold
#SBATCH --time=48:00:00
#SBATCH --cpus-per-task=10
#SBATCH --mem-per-cpu=7G
#SBATCH --gpus=1
#
#SBATCH --partition=owners
#SBATCH --constraint="(GPU_SKU:A100_PCIE|GPU_SKU:A100_SXM4)&CPU_GEN:RME"

set -e
set -x

# There is no constraint to use nodes with large SSD, so instead use the 
# RME cpu constraint.  RME cpus are on machines with large local SSD.

# This path is a symbolic link.  Use realpath to resolve, as the full
# name of the container is used for tracking software version.
CONTAINER=$(realpath "${GROUP_HOME}/projects/alphafold/singularity/alphafold.sif")

singularity run \
    --nv \
    --pwd /app/alphafold \
    "${CONTAINER}" \
    --input_path "${HOME}/projects/alphafold/fasta" \
    --output_path "${HOME}/projects/alphafold/output" \
    --max_template_date 2100-01-01 \
    --preset reduced_dbs \
    --fasta_names ChRmine
