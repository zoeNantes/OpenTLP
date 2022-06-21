# Demonstration of dyngraph2vec

import torch
import torch.optim as optim
from dyngraph2vec.modules import *
from dyngraph2vec.loss import *
from utils import *

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# ====================
data_name = 'Mesh-1'
num_nodes = 38 # Number of nodes (Level-1 w/ fixed node set)
num_snaps = 445 # Number of snapshots
max_thres = 2000 # Threshold for maximum edge weight
struc_dims = [num_nodes, 32] # Layer configuration of structural encoder (FC)
temp_dims = [struc_dims[-1], 16, 16] # Layer configuration of temporal encoder (RNN)
dec_dims = [temp_dims[-1], 32, num_nodes] # Layer configuration of decoder (FC)
beta = 0.1 # Hyper-parameter of loss

# ====================
edge_seq = np.load('data/%s_edge_seq.npy' % (data_name), allow_pickle=True)

# ====================
dropout_rate = 0.2 # Dropout rate
epsilon = 1e-2 # Threshold of zero-refining
win_size = 10 # Window size of historical snapshots
batch_size = 1 # Batch size
num_epochs = 100 # Number of training epochs
num_val_snaps = 10 # Number of validation snapshots
num_test_snaps = 50 # Number of test snapshots
num_train_snaps = num_snaps-num_test_snaps-num_val_snaps # Number of training snapshots

# ====================
# Define the model
model = dyngraph2vec(struc_dims, temp_dims, dec_dims, dropout_rate).to(device)
# ==========
# Define the optimizer
opt = optim.Adam(model.parameters(), lr=1e-4, weight_decay=5e-4)

# ====================
for epoch in range(num_epochs):
    # ====================
    # Train the model
    model.train()
    num_batch = int(np.ceil(num_train_snaps/batch_size)) # Number of batch
    total_loss = 0.0
    for b in range(num_batch):
        start_idx = b*batch_size
        end_idx = (b+1)*batch_size
        if end_idx>num_train_snaps:
            end_idx = num_train_snaps
        # ====================
        # Training for current batch
        batch_loss = 0.0
        for tau in range(start_idx, end_idx):
            # ==========
            adj_list = []  # List of historical adjacency matrices
            for t in range(tau-win_size, tau):
                edges = edge_seq[t]
                adj = get_adj_wei(edges, num_nodes, max_thres)
                adj_norm = adj/max_thres # Normalize the edge weights to [0, 1]
                adj_tnr = torch.FloatTensor(adj_norm).to(device)
                adj_list.append(adj_tnr)
            # ==========
            edges = edge_seq[tau]
            gnd = get_adj_wei(edges, num_nodes, max_thres) # Training ground-truth
            gnd_norm = gnd/max_thres  # Normalize the edge weights (in ground-truth) to [0, 1]
            gnd_tnr = torch.FloatTensor(gnd_norm).to(device)
            # ==========
            adj_est = model(adj_list)
            loss_ = get_d2v_loss(adj_est, gnd_tnr, beta)
            batch_loss = batch_loss + loss_
        # ==========
        # Update model parameter according to batch loss
        opt.zero_grad()
        batch_loss.backward()
        opt.step()
        total_loss = total_loss + batch_loss
    print('Epoch %d Total Loss %f' % (epoch, total_loss))

    # ====================
    # Validate the model
    model.eval()
    RMSE_list = []
    MAE_list = []
    for tau in range(num_snaps-num_test_snaps-num_val_snaps, num_snaps-num_test_snaps):
        # ====================
        adj_list = [] # List of historical adjacency matrices
        for t in range(tau-win_size, tau):
            # ==========
            edges = edge_seq[t]
            adj = get_adj_wei(edges, num_nodes, max_thres)
            adj_norm = adj/max_thres # Normalize the edge weights to [0, 1]
            adj_tnr = torch.FloatTensor(adj_norm).to(device)
            adj_list.append(adj_tnr)
        # ====================
        # Get the prediction result
        adj_est = model(adj_list)
        if torch.cuda.is_available():
            adj_est = adj_est.cpu().data.numpy()
        else:
            adj_est = adj_est.data.numpy()
        adj_est *= max_thres # Rescale edge weights to the original value range
        # ==========
        # Refine the prediction result
        adj_est = (adj_est+adj_est.T)/2
        for r in range(num_nodes):
            adj_est[r, r] = 0
        for r in range(num_nodes):
            for c in range(num_nodes):
                if adj_est[r, c] <= epsilon:
                    adj_est[r, c] = 0
        # ====================
        # Get ground-truth
        edges = edge_seq[tau]
        gnd = get_adj_wei(edges, num_nodes, max_thres)
        # ====================
        # Evaluate the quality of current prediction operation
        RMSE = get_RMSE(adj_est, gnd, num_nodes)
        MAE = get_MAE(adj_est, gnd, num_nodes)
        RMSE_list.append(RMSE)
        MAE_list.append(MAE)
    # ====================
    RMSE_mean = np.mean(RMSE_list)
    RMSE_std = np.std(RMSE_list, ddof=1)
    MAE_mean = np.mean(MAE_list)
    MAE_std = np.std(MAE_list, ddof=1)
    print('Val Epoch %d RMSE %f %f MAE %f %f' % (epoch, RMSE_mean, RMSE_std, MAE_mean, MAE_std))

    # ====================
    # Test the model
    model.eval()
    RMSE_list = []
    MAE_list = []
    for tau in range(num_snaps-num_test_snaps, num_snaps):
        # ====================
        adj_list = []  # List of historical adjacency matrices
        for t in range(tau-win_size, tau):
            # ==========
            edges = edge_seq[t]
            adj = get_adj_wei(edges, num_nodes, max_thres)
            adj_norm = adj/max_thres # Normalize the edge weights to [0, 1]
            adj_tnr = torch.FloatTensor(adj_norm).to(device)
            adj_list.append(adj_tnr)
        # ====================
        # Get the prediction result
        adj_est = model(adj_list)
        if torch.cuda.is_available():
            adj_est = adj_est.cpu().data.numpy()
        else:
            adj_est = adj_est.data.numpy()
        adj_est *= max_thres # Rescale the edge weights to the original value range
        # ==========
        # Refine the prediction result
        adj_est = (adj_est+adj_est.T)/2
        for r in range(num_nodes):
            adj_est[r, r] = 0
        for r in range(num_nodes):
            for c in range(num_nodes):
                if adj_est[r, c] <= epsilon:
                    adj_est[r, c] = 0
        # ====================
        # Get the ground-truth
        edges = edge_seq[tau]
        gnd = get_adj_wei(edges, num_nodes, max_thres)
        # ====================
        # Evaluate the quality of current prediction operation
        RMSE = get_RMSE(adj_est, gnd, num_nodes)
        MAE = get_MAE(adj_est, gnd, num_nodes)
        RMSE_list.append(RMSE)
        MAE_list.append(MAE)
    # ====================
    RMSE_mean = np.mean(RMSE_list)
    RMSE_std = np.std(RMSE_list, ddof=1)
    MAE_mean = np.mean(MAE_list)
    MAE_std = np.std(MAE_list, ddof=1)
    print('Test Epoch %d RMSE %f %f MAE %f %f' % (epoch, RMSE_mean, RMSE_std, MAE_mean, MAE_std))
    print()
