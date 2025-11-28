#!/usr/bin/env python3
"""
ZK-SNARK Benchmark Script
=========================

Benchmarks proving time for Civium compliance circuits.
Target: <5 seconds proving time.

Usage:
    python scripts/benchmark_zk.py [--iterations N] [--circuit NAME]

Requirements:
    - Node.js 18+
    - snarkjs installed globally
    - Circuits compiled (run: npm run setup in circuits/)
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.zk.prover import ComplianceProver


# Configuration
TARGET_TIME_MS = 5000
DEFAULT_ITERATIONS = 10


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    circuit: str
    iterations: int
    min_ms: int
    max_ms: int
    mean_ms: float
    median_ms: float
    p95_ms: int
    p99_ms: int
    success_rate: float
    pass_target: bool


def percentile(data: list[int], p: int) -> int:
    """Calculate percentile."""
    sorted_data = sorted(data)
    index = int(len(sorted_data) * p / 100)
    return sorted_data[min(index, len(sorted_data) - 1)]


async def benchmark_threshold(prover: ComplianceProver, iterations: int) -> BenchmarkResult:
    """Benchmark threshold proof generation."""
    times: list[int] = []
    successes = 0
    
    print(f"\n{'='*60}")
    print(f"Benchmarking: compliance_threshold")
    print(f"Iterations: {iterations}")
    print(f"{'='*60}")
    
    for i in range(iterations):
        score = random.randint(7000, 10000)
        threshold = random.randint(5000, score)
        entity_id = f"BENCH-ENTITY-{i:05d}"
        
        try:
            start = time.time()
            proof = await prover.prove_threshold(
                score=score,
                threshold=threshold,
                entity_id=entity_id,
            )
            duration_ms = int((time.time() - start) * 1000)
            times.append(duration_ms)
            successes += 1
            
            status = "✓" if duration_ms < TARGET_TIME_MS else "✗"
            print(f"  [{i+1}/{iterations}] {status} {duration_ms}ms (score={score}, threshold={threshold})")
            
        except Exception as e:
            print(f"  [{i+1}/{iterations}] ✗ FAILED: {e}")
    
    if not times:
        return BenchmarkResult(
            circuit="compliance_threshold",
            iterations=iterations,
            min_ms=0,
            max_ms=0,
            mean_ms=0,
            median_ms=0,
            p95_ms=0,
            p99_ms=0,
            success_rate=0,
            pass_target=False,
        )
    
    return BenchmarkResult(
        circuit="compliance_threshold",
        iterations=iterations,
        min_ms=min(times),
        max_ms=max(times),
        mean_ms=statistics.mean(times),
        median_ms=statistics.median(times),
        p95_ms=percentile(times, 95),
        p99_ms=percentile(times, 99),
        success_rate=successes / iterations,
        pass_target=percentile(times, 95) < TARGET_TIME_MS,
    )


async def benchmark_range(prover: ComplianceProver, iterations: int) -> BenchmarkResult:
    """Benchmark range proof generation."""
    times: list[int] = []
    successes = 0
    
    print(f"\n{'='*60}")
    print(f"Benchmarking: range_proof")
    print(f"Iterations: {iterations}")
    print(f"{'='*60}")
    
    for i in range(iterations):
        min_score = random.randint(0, 5000)
        max_score = random.randint(min_score + 1000, 10000)
        score = random.randint(min_score, max_score)
        entity_id = f"BENCH-ENTITY-{i:05d}"
        
        try:
            start = time.time()
            proof = await prover.prove_range(
                score=score,
                min_score=min_score,
                max_score=max_score,
                entity_id=entity_id,
            )
            duration_ms = int((time.time() - start) * 1000)
            times.append(duration_ms)
            successes += 1
            
            status = "✓" if duration_ms < TARGET_TIME_MS else "✗"
            print(f"  [{i+1}/{iterations}] {status} {duration_ms}ms (range=[{min_score},{max_score}], score={score})")
            
        except Exception as e:
            print(f"  [{i+1}/{iterations}] ✗ FAILED: {e}")
    
    if not times:
        return BenchmarkResult(
            circuit="range_proof",
            iterations=iterations,
            min_ms=0,
            max_ms=0,
            mean_ms=0,
            median_ms=0,
            p95_ms=0,
            p99_ms=0,
            success_rate=0,
            pass_target=False,
        )
    
    return BenchmarkResult(
        circuit="range_proof",
        iterations=iterations,
        min_ms=min(times),
        max_ms=max(times),
        mean_ms=statistics.mean(times),
        median_ms=statistics.median(times),
        p95_ms=percentile(times, 95),
        p99_ms=percentile(times, 99),
        success_rate=successes / iterations,
        pass_target=percentile(times, 95) < TARGET_TIME_MS,
    )


async def benchmark_tier(prover: ComplianceProver, iterations: int) -> BenchmarkResult:
    """Benchmark tier proof generation."""
    times: list[int] = []
    successes = 0
    
    tier_bounds = {
        1: (9500, 10000),
        2: (8500, 9499),
        3: (7000, 8499),
        4: (5000, 6999),
        5: (0, 4999),
    }
    
    print(f"\n{'='*60}")
    print(f"Benchmarking: tier_membership")
    print(f"Iterations: {iterations}")
    print(f"{'='*60}")
    
    for i in range(iterations):
        tier = random.randint(1, 5)
        min_score, max_score = tier_bounds[tier]
        score = random.randint(min_score, max_score)
        entity_id = f"BENCH-ENTITY-{i:05d}"
        
        try:
            start = time.time()
            proof = await prover.prove_tier(
                score=score,
                tier=tier,
                entity_id=entity_id,
            )
            duration_ms = int((time.time() - start) * 1000)
            times.append(duration_ms)
            successes += 1
            
            status = "✓" if duration_ms < TARGET_TIME_MS else "✗"
            print(f"  [{i+1}/{iterations}] {status} {duration_ms}ms (tier={tier}, score={score})")
            
        except Exception as e:
            print(f"  [{i+1}/{iterations}] ✗ FAILED: {e}")
    
    if not times:
        return BenchmarkResult(
            circuit="tier_membership",
            iterations=iterations,
            min_ms=0,
            max_ms=0,
            mean_ms=0,
            median_ms=0,
            p95_ms=0,
            p99_ms=0,
            success_rate=0,
            pass_target=False,
        )
    
    return BenchmarkResult(
        circuit="tier_membership",
        iterations=iterations,
        min_ms=min(times),
        max_ms=max(times),
        mean_ms=statistics.mean(times),
        median_ms=statistics.median(times),
        p95_ms=percentile(times, 95),
        p99_ms=percentile(times, 99),
        success_rate=successes / iterations,
        pass_target=percentile(times, 95) < TARGET_TIME_MS,
    )


def print_results(results: list[BenchmarkResult]) -> bool:
    """Print benchmark results summary."""
    print(f"\n{'='*70}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*70}")
    
    print(f"\n{'Circuit':<25} | {'P95':>8} | {'Mean':>8} | {'Target':>8} | Status")
    print("-" * 70)
    
    all_pass = True
    for r in results:
        status = "✅ PASS" if r.pass_target else "❌ FAIL"
        if not r.pass_target:
            all_pass = False
        print(f"{r.circuit:<25} | {r.p95_ms:>6}ms | {r.mean_ms:>6.0f}ms | <{TARGET_TIME_MS}ms | {status}")
    
    print()
    
    # Detailed stats
    for r in results:
        print(f"\n{r.circuit}:")
        print(f"  Iterations:   {r.iterations}")
        print(f"  Success rate: {r.success_rate*100:.1f}%")
        print(f"  Min:          {r.min_ms}ms")
        print(f"  Max:          {r.max_ms}ms")
        print(f"  Mean:         {r.mean_ms:.0f}ms")
        print(f"  Median:       {r.median_ms:.0f}ms")
        print(f"  P95:          {r.p95_ms}ms")
        print(f"  P99:          {r.p99_ms}ms")
    
    print()
    return all_pass


async def main():
    parser = argparse.ArgumentParser(description="Benchmark ZK-SNARK proof generation")
    parser.add_argument("--iterations", "-n", type=int, default=DEFAULT_ITERATIONS,
                       help=f"Number of iterations (default: {DEFAULT_ITERATIONS})")
    parser.add_argument("--circuit", "-c", type=str, choices=["threshold", "range", "tier"],
                       help="Benchmark specific circuit only")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file for results")
    
    args = parser.parse_args()
    
    print("╔" + "═"*58 + "╗")
    print("║  CIVIUM ZK-SNARK BENCHMARK                               ║")
    print(f"║  Target: <{TARGET_TIME_MS}ms proving time                            ║")
    print("╚" + "═"*58 + "╝")
    
    # Initialize prover
    try:
        prover = ComplianceProver()
    except Exception as e:
        print(f"\n❌ Failed to initialize prover: {e}")
        print("   Make sure circuits are compiled: cd circuits && npm run setup")
        sys.exit(1)
    
    results: list[BenchmarkResult] = []
    
    # Run benchmarks
    if args.circuit is None or args.circuit == "threshold":
        results.append(await benchmark_threshold(prover, args.iterations))
    
    if args.circuit is None or args.circuit == "range":
        results.append(await benchmark_range(prover, args.iterations))
    
    if args.circuit is None or args.circuit == "tier":
        results.append(await benchmark_tier(prover, args.iterations))
    
    # Print summary
    all_pass = print_results(results)
    
    # Save results if requested
    if args.output:
        output_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target_ms": TARGET_TIME_MS,
            "results": [
                {
                    "circuit": r.circuit,
                    "iterations": r.iterations,
                    "min_ms": r.min_ms,
                    "max_ms": r.max_ms,
                    "mean_ms": r.mean_ms,
                    "median_ms": r.median_ms,
                    "p95_ms": r.p95_ms,
                    "p99_ms": r.p99_ms,
                    "success_rate": r.success_rate,
                    "pass_target": r.pass_target,
                }
                for r in results
            ],
            "all_pass": all_pass,
        }
        
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Results saved to: {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())

