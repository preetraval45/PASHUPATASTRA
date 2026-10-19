# RP-08 — PyTorch and backpropagation

Study notes for the owner's RP-08 learning task. It is done when **you** write
a training loop from memory and train it, so use this as a map, then close
it and write the loop yourself.

## 1. What backpropagation does

A network is a chain of functions. The loss L is a number at the end of it.
Training adjusts every weight w a little in the direction that lowers L:

    w ← w − learning_rate · ∂L/∂w

Backpropagation computes every ∂L/∂w in one backward pass by applying the
chain rule from the loss back to the inputs. Each operation only needs its own
local derivative, multiplied by the gradient arriving from above. Karpathy's
*micrograd* builds exactly this in about 100 lines. Build it, and the rest of
PyTorch stops being magic.

## 2. The five pieces of every PyTorch training loop

| Piece | What it is | Where it appears in this repository |
|---|---|---|
| `Dataset` / batches | indexable examples; batches are stacked tensors | `sati/lm/train.py` `batches()` |
| `nn.Module` | parameters plus `forward()` | `sati/lm/model.py` `Kushmanda`, `sati/embed/model.py` `Encoder` |
| Loss | one number to minimise | `F.cross_entropy` (model.py), `info_nce` (embed/model.py) |
| Optimizer | applies the update rule | `torch.optim.AdamW` (train.py) |
| Loop | `zero_grad → forward → loss.backward() → step` | `train.py` main loop |

The core loop, in order:

    for batch in data:
        optimizer.zero_grad()        # gradients accumulate unless cleared
        loss = loss_fn(model(x), y)  # forward
        loss.backward()              # backprop: fills .grad on every parameter
        optimizer.step()             # update the weights

## 3. Things the exercise will test

- **Validation, not training, loss decides when to stop.** Brahmacharini picks
  its epoch on validation sources, never on the test set.
- **`model.eval()` and `torch.no_grad()` for evaluation.** The first turns off
  dropout; the second stops gradients being built. `held_out_loss` in
  train.py does both.
- **Checkpoint the best model, not the last.** See how `best_state` is kept in
  `sati/embed/run.py`.
- **Gradient clipping** (`clip_grad_norm_`) stops one bad batch from blowing
  up training (train.py).

## Check yourself (the done-when)

Without looking:
1. Write the training loop for a small classifier on any public dataset (for
   example MNIST or the scikit-learn digits), with train and validation splits
   and a saved checkpoint.
2. Explain why `optimizer.zero_grad()` is needed.
3. Explain what `loss.backward()` puts where.
