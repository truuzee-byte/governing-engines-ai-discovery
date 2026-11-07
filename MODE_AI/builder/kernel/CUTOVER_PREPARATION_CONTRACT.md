# Builder / external Kernel preparation boundary

Normal Builder still selects BootstrapKernelClient. That adapter invokes local
workspace, file and command primitives with host-user authority. This phase does
not activate protected execution or imply host confinement.

The existing cutover point is `run_builder_core(require_kernel=True,
kernel_client=<OperationBoundKernelClient>)`. Required mode rejects an absent or
incompatible client before workspace mutation; an external rejection must never
fall back to BootstrapKernelClient. HttpKernelClient remains explicitly unusable
until an authenticated compatible contract is deployed.

BuilderKernelCutoverPreparation/1 binds the complete canonical plan hash, snapshot,
repository target, CREATE/MODIFY map, directories, commands and required outputs.
It records proof obligations without executing anything. Existing Builder output
capture, artifact hashes, validation, Observation custody and terminal receipt
checks remain required. Kernel command evidence must retain release/retirement
state; UNPROVEN release cannot become PASS.

Preparation is not activation readiness. The external Kernel's current command
profile expressly excludes script/module/pytest launch policy and does not supply
the complete Builder artifact-transfer surface. Implementing a guessed transport
or widening that profile would cross the protected contract boundary. The current
preparation therefore says boundary_ready_for_activation=false even though its
read-only plan preparation is complete.

Later activation requires compatible admitted artifact transfer, authenticated
operation-bound execution, exact returned output/hash/evidence custody, cleanup
and release proof, qualified checkpoint deployment and explicit authority. A
failed cutover cannot be repaired by silently returning to host execution.
Rollback of produced artifacts requires separately authorized file authority;
checkpoint rollback is never a recovery mechanism.
