%Demonstration of AM-NMF
clear;

%====================
data_name = 'Enron';
num_nodes = 184; %Number of nodes (i.e., fixed node set in Level-1)
num_snaps = 26; %Number of snapshots (time steps)
hid_dim = 64; %Latent representation (embedding) dimensionality
win_size = 5; %Window size
alpha = 0.1;
beta = 1e-6;
theta = 0.1;
max_iter = 1e3; %Maximum number of iterations
min_error = 1e-6; %Minimum relative error to determine convergence

%====================
data = load(['data/', data_name, '.mat']);
adj_seq_gbl = data.adj_seq;
clear data;

%====================
AUC_seq = [];
for tau=win_size:num_snaps-1
    gnd = adj_seq_gbl{tau+1}; %Ground-truth for evaluation
    gnd = full(gnd);
    adj_seq = cell(win_size);
    idx = 1;
    for t=tau-win_size+1:tau
        adj_seq{idx} = adj_seq_gbl{t};
        idx = idx+1;
    end
    adj_est = AM_NMF(adj_seq,hid_dim,win_size,alpha,min_error,max_iter,1,theta,beta);
    adj_est = full(adj_est);
    adj_est = (adj_est + adj_est')/2;
    %==========
    %Evaluate the quality of current prediction operation
    [X,Y,T,AUC] = perfcurve(reshape(gnd, [1, num_nodes^2]), reshape(adj_est, [1, num_nodes^2]), 1);
    AUC_seq = [AUC_seq, AUC];
    fprintf('Snap#%d AUC %.4f\n', [tau, AUC]);
    
end
AUC_mean = mean(AUC_seq);
AUC_std = std(AUC_seq);
