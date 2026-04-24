import numpy as np
import networkx as nx
from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.circuit.library import QAOAAnsatz
from qiskit_optimization.applications import Tsp
from qiskit_optimization.converters import QuadraticProgramToQubo
from qiskit import transpile
# --- 1. SETUP THE MAP (3 Cities) ---
n = 3
G = nx.Graph()
G.add_nodes_from(range(n))
# A simple triangle: Distance 1.0 between everyone
edges = [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 1.0)]
for u, v, w in edges:
    G.add_edge(u, v, weight=w)

print(f"--- Setting up TSP for {n} Cities ({n**2} Qubits) ---")

# --- 2. GENERATE THE HAMILTONIAN (The "Cost Layer" Logic) ---
# Instead of writing CNOTs manually, we let Qiskit calculate the Pauli operators.
# This includes the PENALTY logic automatically.
tsp = Tsp(G)
qp = tsp.to_quadratic_program()

# *** CRITICAL PART ***
# We convert the math problem to a 'QUBO' (Quantum/Ising) problem.
# We set a HIGH penalty so the solver learns "Cheating is bad".
converter = QuadraticProgramToQubo(penalty=10.0) 
qubo = converter.convert(qp)
qubit_op, offset = qubo.to_ising()

print(f"Operator Created. Number of Qubits: {qubit_op.num_qubits}")

# --- 3. DEFINE THE CIRCUIT BUILDER ---
def get_qaoa_circuit(angles):
    """
    Builds the QAOA circuit.
    angles[0] = gamma (Cost Layer time)
    angles[1] = beta  (Mixer Layer time)
    """
    # Qiskit has a built-in function that does the "CNOT-RZ-CNOT" stuff for us
    # based on the Hamiltonian (qubit_op) we created above.
    ansatz = QAOAAnsatz(cost_operator=qubit_op, reps=3, name='qaoa')
    ansatz.measure_all()
    
    # Bind the angles to the circuit
    # QAOAAnsatz expects a flat list of parameters
    d = len(angles) // 2
    # We simply assign our [gamma, beta] to the circuit
    bound_circuit = ansatz.assign_parameters(angles)
    return bound_circuit

# --- 4. DEFINE THE OBJECTIVE FUNCTION (ENERGY) ---
sim = AerSimulator()

def objective_function(angles):
    qc = get_qaoa_circuit(angles)
    
    # --- THE FIX: UNPACK THE CIRCUIT ---
    # Convert the high-level 'qaoa' block into standard gates (CX, RZ, etc.)
    qc_transpiled = transpile(qc, sim) 
    
    # Run Simulation using the TRANSPILIED circuit
    counts = sim.run(qc_transpiled, shots=2048).result().get_counts()
    
    total_energy = 0
    total_shots = 0
    
    for bitstring, count in counts.items():
        x = np.array([int(bit) for bit in bitstring])
        energy_of_state = qp.objective.evaluate(x)
        total_energy += (energy_of_state * count)
        total_shots += count
            
    avg_energy = total_energy / total_shots
    return avg_energy

# --- 5. THE OPTIMIZATION LOOP ---
print("\nStarting Optimizer... (This might take 10-20 seconds)")
initial_guess = [0.1, 0.1]*3 # [Gamma, Beta]
res = minimize(objective_function, initial_guess, method='COBYLA', options={'maxiter': 30})

print("-" * 30)
print("Optimal Angles:", res.x)
print("Best Energy:", res.fun)
print("-" * 30)

# --- 6. DECODING THE RESULT ---
print("\nAnalyzing Final Result...")
print("\nAnalyzing Final Result...")
best_qc = get_qaoa_circuit(res.x)

# *** ADD THIS LINE ***
best_qc_transpiled = transpile(best_qc, sim) 
# *********************

# Run the TRANSPILIED circuit, not the original 'best_qc'
final_counts = sim.run(best_qc_transpiled, shots=4096).result().get_counts()

# Sort to find the most frequent bitstring
sorted_counts = sorted(final_counts.items(), key=lambda x: x[1], reverse=True)
best_bitstring = sorted_counts[0][0]

print(f"Most Frequent Bitstring: {best_bitstring}")

# Visualize as Matrix
x = np.array([int(bit) for bit in best_bitstring])
# Use Qiskit's helper to interpret the bits into a route
# Note: Tsp.interpret helps us decode the "Grid"
try:
    route_order = tsp.interpret(x)
    print("Route Order Indices:", route_order)
    print("SUCCESS! A valid tour was found.")
except:
    print("FAILURE: The solver found an invalid state (Penalties were too weak?).")