//! Benchmark for ZK-SNARK proving time
//!
//! Target: <5 seconds for all circuit types

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use civium_zk_prover::{
    circuits::{ThresholdCircuit, RangeCircuit, TierCircuit},
    types::{ThresholdInput, RangeInput, TierInput},
};
use ark_bn254::{Bn254, Fr};
use ark_groth16::Groth16;
use ark_snark::SNARK;
use ark_std::rand::thread_rng;
use std::time::Duration;

const TARGET_TIME_SECS: u64 = 5;

/// Benchmark threshold circuit proving
fn bench_threshold_proving(c: &mut Criterion) {
    let mut group = c.benchmark_group("threshold_proving");
    group.measurement_time(Duration::from_secs(30));
    group.sample_size(10);

    let scores = [5000u64, 7500, 9000, 9999];
    
    for score in scores {
        let circuit = ThresholdCircuit::new(
            5000,
            Fr::from(123456789012345678u64),
            score,
            Fr::from(987654321098765432u64),
        );

        group.bench_with_input(
            BenchmarkId::new("score", score),
            &circuit,
            |b, circuit| {
                let mut rng = thread_rng();
                
                // Setup (not part of benchmark)
                let (pk, _vk) = Groth16::<Bn254>::circuit_specific_setup(
                    circuit.clone(),
                    &mut rng,
                ).unwrap();

                b.iter(|| {
                    let circuit = black_box(circuit.clone());
                    let _proof = Groth16::<Bn254>::prove(&pk, circuit, &mut rng).unwrap();
                });
            },
        );
    }

    group.finish();
}

/// Benchmark range circuit proving
fn bench_range_proving(c: &mut Criterion) {
    let mut group = c.benchmark_group("range_proving");
    group.measurement_time(Duration::from_secs(30));
    group.sample_size(10);

    let ranges = [(5000, 8000), (7000, 9000), (0, 10000)];
    
    for (min, max) in ranges {
        let score = (min + max) / 2;
        let circuit = RangeCircuit::new(
            min,
            max,
            Fr::from(123456789012345678u64),
            score,
            Fr::from(987654321098765432u64),
        );

        group.bench_with_input(
            BenchmarkId::new("range", format!("{}-{}", min, max)),
            &circuit,
            |b, circuit| {
                let mut rng = thread_rng();
                
                let (pk, _vk) = Groth16::<Bn254>::circuit_specific_setup(
                    circuit.clone(),
                    &mut rng,
                ).unwrap();

                b.iter(|| {
                    let circuit = black_box(circuit.clone());
                    let _proof = Groth16::<Bn254>::prove(&pk, circuit, &mut rng).unwrap();
                });
            },
        );
    }

    group.finish();
}

/// Benchmark tier circuit proving
fn bench_tier_proving(c: &mut Criterion) {
    let mut group = c.benchmark_group("tier_proving");
    group.measurement_time(Duration::from_secs(30));
    group.sample_size(10);

    let tier_scores = [(1, 9700), (2, 8700), (3, 7500), (4, 6000), (5, 3000)];
    
    for (tier, score) in tier_scores {
        let circuit = TierCircuit::new(
            tier,
            Fr::from(123456789012345678u64),
            score,
            Fr::from(987654321098765432u64),
        );

        group.bench_with_input(
            BenchmarkId::new("tier", tier),
            &circuit,
            |b, circuit| {
                let mut rng = thread_rng();
                
                let (pk, _vk) = Groth16::<Bn254>::circuit_specific_setup(
                    circuit.clone(),
                    &mut rng,
                ).unwrap();

                b.iter(|| {
                    let circuit = black_box(circuit.clone());
                    let _proof = Groth16::<Bn254>::prove(&pk, circuit, &mut rng).unwrap();
                });
            },
        );
    }

    group.finish();
}

/// Benchmark verification time
fn bench_verification(c: &mut Criterion) {
    let mut group = c.benchmark_group("verification");
    group.measurement_time(Duration::from_secs(20));

    let circuit = ThresholdCircuit::new(
        8000,
        Fr::from(123456789012345678u64),
        8500,
        Fr::from(987654321098765432u64),
    );

    let mut rng = thread_rng();
    let (pk, vk) = Groth16::<Bn254>::circuit_specific_setup(circuit.clone(), &mut rng).unwrap();
    let proof = Groth16::<Bn254>::prove(&pk, circuit.clone(), &mut rng).unwrap();
    let public_inputs = vec![Fr::from(8000u64), Fr::from(123456789012345678u64)];

    group.bench_function("groth16_verify", |b| {
        b.iter(|| {
            let result = Groth16::<Bn254>::verify(
                black_box(&vk),
                black_box(&public_inputs),
                black_box(&proof),
            ).unwrap();
            assert!(result);
        });
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_threshold_proving,
    bench_range_proving,
    bench_tier_proving,
    bench_verification,
);

criterion_main!(benches);

