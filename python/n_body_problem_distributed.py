import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpi4py import MPI
import time

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
    

def calculate_accelerations(positions, masses):
    """
    Calculate the acceleration of each bodies in the system
    positions: positions of all bodies, a 2D numpy array of shape (n, 2)
    masses: masses of all bodies, a 1D numpy array of shape (n,)
    rank: the rank of the current process
    size: the total number of processes
    """

    G = 6.67430e-11 # Newton's gravitational constant

    local_positions = positions[rank::size, :] # Slice of positions for the current process

    n = local_positions.shape[0]
    local_accelerations = np.zeros((n, 2))

    for i in range(n):
        for j, mass in enumerate(masses):
            if i != j:
                dx = positions[j, 0] - local_positions[i, 0]
                dy = positions[j, 1] - local_positions[i, 1]
                distance = np.sqrt(dx**2 + dy**2)
                if distance > 0: # Avoid division by zero
                    force = G * mass / distance ** 2
                    local_accelerations[i, 0] += force * dx / distance
                    local_accelerations[i, 1] += force * dy / distance

    accelerations = np.zeros_like(positions, dtype=np.float64)
    for i in range(n):
        accelerations[rank + i * size, :] = local_accelerations[i, :]

    return accelerations

start_time = time.time()
frame_count = 0

def main():
    """ N-body problem simulation """
    global frame_count

    # Simulation parameters
    N = 1000 # Number of bodies
    t = 0 # Current time of the simulation
    t_end = 1 # End time of the simulation
    dt = 1.0 / 60 # Time step

    # Prep figure
    fig , ax = plt.subplots()
    fig.canvas.mpl_connect('close_event', on_close)

    # Initialize everything in the root process
    if comm.rank == 0:
        # Initial conditions
        positions = np.random.randn(N, 2) * 100
        masses = np.random.rand(N)
        velocities = np.random.randn(N, 2) * 100

        # Convert to Center-of-Mass frame
        # velocities -= np.mean(masses * velocities,0) / np.mean(masses)
    else:
        positions = None
        masses = None
        velocities = None
    
    # Broadcast initial conditions to all processes
    positions = comm.bcast(positions, root=0)
    masses = comm.bcast(masses, root=0)
    velocities = comm.bcast(velocities, root=0)

    # Main loop
    while t <= t_end:
        ## Updateing positions using a leap-frog scheme

        # Calculate accelerations
        local_accelerations = calculate_accelerations(positions, masses)

        # Gather accelerations from all processes
        if comm.rank == 0:
            all_accelerations = np.zeros_like(local_accelerations, dtype=np.float64)
        else:
            all_accelerations = None
            
        comm.Reduce(local_accelerations, all_accelerations, op=MPI.SUM, root=0)

        if comm.rank == 0:
            # Half-kick step
            velocities += 0.5 * dt * all_accelerations

            # Drift step
            positions += dt * velocities

            # Broadcast new positions all processes
            comm.Bcast(positions, root=0)

        comm.Barrier()

        # Calculate updated accelerations
        local_accelerations = calculate_accelerations(positions, masses)

        # Gather accelerations from all processes
        if comm.rank == 0:
            all_accelerations = np.zeros_like(local_accelerations)
        
        comm.Reduce(local_accelerations, all_accelerations, op=MPI.SUM, root=0)

        if comm.rank == 0:
            # Second half-kick step
            velocities += 0.5 * dt * all_accelerations
            
            # Update time
            t += dt

            # Plot in real time
            ax.clear()
            colors = cm.rainbow(np.linspace(0, 1, positions.shape[0]))
            ax.scatter(positions[:, 0], positions[:, 1], s=masses * 100, c=colors)
            ax.set_title(f"t = {t:.2f}")
            ax.grid(False)
            ax.set_facecolor('black')
            plt.pause(0.01)

            frame_count += 1

def on_close(_):
    '''
    Calculate the average fps when the window is closed
    '''
    if comm.rank == 0:
        end_time = time.time()
        duration = end_time - start_time
        avg_fps = frame_count / duration
        print(f"Average FPS: {avg_fps:.2f}")
    exit()

if __name__ == "__main__":
    main()
