import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from matplotlib.colors import TwoSlopeNorm
from torch import optim
import matplotlib.pyplot as plt
from torchvision import datasets
from torchvision import transforms
from accelerate import Accelerator
import numpy as np

class MNIST_linear(nn.Module):
    def __init__(self):
        super().__init__()
        self.flat = nn.Flatten()
        self.net = nn.Linear(784, 10, bias=False)
    
    def forward(self, x):
        return self.net(self.flat(x))
    
    def re_init(self):
        nn.init.normal_(self.net.weight)

class test_with_noise():
    def __init__(self, noise, model):
        self.MNIST_test = datasets.MNIST(
            root="../datasets/",
            train=False,
            download=True,
            transform=transforms.ToTensor()
        )
        self.accelerator = Accelerator()
        self.device = self.accelerator.device
        self.loss_fn = nn.CrossEntropyLoss()
        self.test_loader = DataLoader(self.MNIST_test, 128)
        self.test_loader = self.accelerator.prepare(self.test_loader)
        self.model_count = 0
        self.noise = noise
        self.model = model.to(self.device)

    def preview_parameters(self):
        for name, param in self.model.named_parameters():
            if 'weight' in name:
                weights = param.cpu().detach().numpy()
                k = weights.shape[1] / weights.shape[0]
                cmap = plt.get_cmap('bwr')
                vmin = weights.min()
                vmax = weights.max()
                if vmin == vmax:
                    norm = None
                else:
                    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

                plt.imshow(weights, cmap=cmap, norm=norm, aspect=k)
                plt.colorbar()
                plt.title(f'Visualization with Noise: {self.noise}')
                plt.show()

    def test(self):
        size = len(self.MNIST_test)
        num_batches = len(self.test_loader)
        self.model.eval()
        tloss, tcorrect = 0.0, 0.0

        for param in self.model.parameters():
            param.data += torch.randn_like(param.data) * self.noise
                    
        with torch.no_grad():
            for X, y in self.test_loader:
                X = X.to(self.device)
                y = y.to(self.device)
                pred = self.model(X)
                tloss += self.loss_fn(pred, y)
                tcorrect += (pred.argmax(1) == y).type(torch.float).sum().item()
        tloss /= num_batches
        tcorrect /= size
        tcorrect *= 100
        print(f"Current Test Error: {tloss:>8f}")
        print(f"Current Test Accuracy: {tcorrect:>0.01f}%")
        self.preview_parameters()
        return tloss.item(), tcorrect

# Load the model
model = MNIST_linear()

path = ../datasets/MNIST_models/0.pt  
model.load_state_dict(torch.load(path).state_dict())

noise = 0
test_with_noise = test_with_noise(noise, model)
noise_values = []
loss_values = []
acc_values = []

#set num_diffusion_timesteps
n=20

config = {
    'diffusion': {
        'noise_schedule_type': 'linear',
        'noise_start': 0.0001,
        'noise_end': 0.02,
        'num_diffusion_timesteps': n
    }
}

def get_noise_schedule(noise_schedule_type, *, noise_start, noise_end, num_diffusion_timesteps):
    if noise_schedule_type == 'linear':
        noises = np.linspace(noise_start, noise_end, num_diffusion_timesteps, dtype=np.float64)
    else:
        raise NotImplementedError(noise_schedule_type)

    assert noises.shape == (num_diffusion_timesteps,)
    return noises

noise_schedule = get_noise_schedule(**config['diffusion'])

#add noise
for i in range(n):
    noise += noise_schedule[i]
    print(f"Current Noise: {noise}")
    test_with_noise.noise = noise
    loss, acc = test_with_noise.test()
    noise_values.append(noise)
    loss_values.append(loss)
    acc_values.append(acc)


# Plot loss and accuracy
plt.figure(figsize=(12, 4))
plt.subplot(1, 2, 1)
plt.plot(noise_values, loss_values, marker='o')
plt.xlabel('Noise')
plt.ylabel('Test Loss')
plt.title('Test Loss with Noise')

plt.subplot(1, 2, 2)
plt.plot(noise_values, acc_values, marker='o', color='r')
plt.xlabel('Noise')
plt.ylabel('Test Accuracy (%)')
plt.title('Test Accuracy with Noise')

plt.tight_layout()
plt.show()
