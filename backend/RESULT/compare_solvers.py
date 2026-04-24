import matplotlib.pyplot as plt
from app.solvers.hybride_solver import GA_QAOA_Solver
from app.solvers.apso_solver import APSO_QAOA_Solver

# Graph data is pulled automatically from graph_world by the solvers

def run_battle():
    cities = ['A', 'B', 'C', 'D']
    p_layers = 2
    generations = 30
    pop_size = 40
    
    print("\n" + "="*40)
    print("ROUND 1: STANDARD GA-QAOA (The Paper)")
    print("="*40)
    ga_solver = GA_QAOA_Solver(cities, pop_size=pop_size, generations=generations, p_layers=p_layers)
    ga_result, ga_history = ga_solver.solve()
    
    print("\n" + "="*40)
    print("ROUND 2: NOVEL APSO-QAOA (Your Thesis)")
    print("="*40)
    apso_solver = APSO_QAOA_Solver(cities, pop_size=pop_size, generations=generations, p_layers=p_layers)
    apso_result, apso_history = apso_solver.solve()
    
    # --- PLOT RESULTS ---
    plt.figure(figsize=(10, 6))
    
    # Plot GA (Blue Dashed)
    plt.plot(ga_history, label='Standard GA (Benchmark)', color='blue', linestyle='--', alpha=0.7)
    
    # Plot APSO (Red Solid)
    plt.plot(apso_history, label='Adaptive PSO (Novel)', color='red', linewidth=2)
    
    plt.title("Convergence Comparison: GA vs APSO for Quantum Control")
    plt.xlabel("Generation")
    plt.ylabel("Energy (Cost)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.savefig("final_comparison.png")
    print("\nGraph saved as 'final_comparison.jpg'")
    
    print(f"GA Final Energy:   {ga_result['energy']:.4f}")
    print(f"APSO Final Energy: {apso_result['energy']:.4f}")
    
    if apso_result['energy'] <= ga_result['energy']:
        print(">>> CONCLUSION: APSO matches or beats the benchmark!")

if __name__ == "__main__":
    run_battle()