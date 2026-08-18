# The AWS enforcement floor.
#
# One IRSA role per agent, mirroring its declared tools, with read and write
# separated — and, underneath all of it, a deny that no future grant can
# override.
#
# The point of this file is that the runtime's guarantees survive a mistake in
# the runtime. `AgentRuntime` refuses an undeclared tool, and Dharma refuses an
# action above an agent's ceiling; both are Python, and Python can be wrong. IAM
# is the floor beneath them: even if an agent were somehow talked into calling
# `DeleteCluster`, the credential it holds cannot perform it.
#
# Two properties are load-bearing:
#
#   1. **Explicit Deny always wins in IAM.** The destructive deny below is
#      attached to every agent role, so no later policy — however it is attached,
#      by whom, or in what environment — can grant those actions. A deny-list is
#      usually the weaker pattern; here it is the only one that cannot be
#      out-voted by a well-meaning Allow added under time pressure.
#
#   2. **The permission set is derived, not written twice.** `agents.json` is
#      shared with the test suite, which asserts the `tools` list matches
#      `sati_roles()` exactly. An agent granted a tool without a matching IAM
#      change fails CI, and so does the reverse.

locals {
  # `_comment` is documentation, not an agent.
  agents = { for name, spec in jsondecode(file("${path.module}/agents.json")) :
    name => spec if name != "_comment"
  }

  # Actions no Pashupatastra role may perform in any environment, ever.
  #
  # Deliberately broader than the action registry's `delete_infrastructure`:
  # the registry governs what the *platform* will choose to do, and this governs
  # what its credentials *can* do. The second must be strictly smaller, or the
  # first is the only thing standing between a bug and a deleted database.
  forbidden_actions = [
    "eks:DeleteCluster",
    "eks:DeleteNodegroup",
    "rds:DeleteDBInstance",
    "rds:DeleteDBCluster",
    "rds:ModifyDBInstance",
    "s3:DeleteBucket",
    "s3:DeleteObject",
    "ec2:TerminateInstances",
    "ec2:DeleteVpc",
    "ec2:DeleteSubnet",
    "iam:*",
    "kms:ScheduleKeyDeletion",
    "kms:DisableKey",
    "cloudtrail:StopLogging",
    "cloudtrail:DeleteTrail",
    "secretsmanager:DeleteSecret",
    "logs:DeleteLogGroup",
  ]
}

# --- trust ---------------------------------------------------------------------

variable "oidc_provider_arn" {
  description = "EKS OIDC provider ARN for IRSA. Empty disables agent role creation, so a cluster-less environment plans clean."
  type        = string
  default     = ""
}

variable "oidc_provider_url" {
  description = "EKS OIDC issuer URL, without the https:// scheme."
  type        = string
  default     = ""
}

variable "agent_namespace" {
  description = "Kubernetes namespace the agent service accounts live in."
  type        = string
  default     = "pashupatastra"
}

# Each role trusts exactly one service account in one namespace. Without the
# `sub` condition any pod in the cluster could assume any agent's role, which
# would make per-agent roles decorative.
data "aws_iam_policy_document" "agent_trust" {
  for_each = var.oidc_provider_arn == "" ? {} : local.agents

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.agent_namespace}:${each.value.service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agent" {
  for_each = var.oidc_provider_arn == "" ? {} : local.agents

  name               = "pashupatastra-${var.environment}-${each.value.service_account}"
  description        = "IRSA role for ${each.key}. Permissions mirror its AgentSpec declaration."
  assume_role_policy = data.aws_iam_policy_document.agent_trust[each.key].json

  # An agent session should not outlive the incident it was created for.
  max_session_duration = 3600
}

# --- the floor ------------------------------------------------------------------

# Attached to every agent role. Explicit Deny beats any Allow, in any policy,
# so this cannot be undone by adding permissions elsewhere.
data "aws_iam_policy_document" "forbidden" {
  statement {
    sid       = "DestructiveActionsDeniedInEveryEnvironment"
    effect    = "Deny"
    actions   = local.forbidden_actions
    resources = ["*"]
  }
}

resource "aws_iam_policy" "forbidden" {
  name        = "pashupatastra-${var.environment}-forbidden"
  description = "Destructive actions denied to every agent role, in every environment. Explicit Deny wins over any Allow."
  policy      = data.aws_iam_policy_document.forbidden.json
}

resource "aws_iam_role_policy_attachment" "forbidden" {
  for_each = var.oidc_provider_arn == "" ? {} : local.agents

  role       = aws_iam_role.agent[each.key].name
  policy_arn = aws_iam_policy.forbidden.arn
}

# --- read and write, separated ---------------------------------------------------

data "aws_iam_policy_document" "agent_read" {
  for_each = { for name, spec in local.agents : name => spec if length(spec.read) > 0 }

  statement {
    sid       = "Read"
    effect    = "Allow"
    actions   = each.value.read
    resources = ["*"]
  }
}

resource "aws_iam_policy" "agent_read" {
  for_each = var.oidc_provider_arn == "" ? {} : {
    for name, spec in local.agents : name => spec if length(spec.read) > 0
  }

  name   = "pashupatastra-${var.environment}-${each.value.service_account}-read"
  policy = data.aws_iam_policy_document.agent_read[each.key].json
}

resource "aws_iam_role_policy_attachment" "agent_read" {
  for_each = var.oidc_provider_arn == "" ? {} : {
    for name, spec in local.agents : name => spec if length(spec.read) > 0
  }

  role       = aws_iam_role.agent[each.key].name
  policy_arn = aws_iam_policy.agent_read[each.key].arn
}

# Separate policies rather than one merged document, so an agent with an empty
# `write` list has no write policy attached at all — its absence is visible in
# `terraform plan` rather than being an empty statement nobody reads.
data "aws_iam_policy_document" "agent_write" {
  for_each = { for name, spec in local.agents : name => spec if length(spec.write) > 0 }

  statement {
    sid       = "Write"
    effect    = "Allow"
    actions   = each.value.write
    resources = ["*"]
  }
}

resource "aws_iam_policy" "agent_write" {
  for_each = var.oidc_provider_arn == "" ? {} : {
    for name, spec in local.agents : name => spec if length(spec.write) > 0
  }

  name   = "pashupatastra-${var.environment}-${each.value.service_account}-write"
  policy = data.aws_iam_policy_document.agent_write[each.key].json
}

resource "aws_iam_role_policy_attachment" "agent_write" {
  for_each = var.oidc_provider_arn == "" ? {} : {
    for name, spec in local.agents : name => spec if length(spec.write) > 0
  }

  role       = aws_iam_role.agent[each.key].name
  policy_arn = aws_iam_policy.agent_write[each.key].arn
}

# --- outputs ---------------------------------------------------------------------

output "agent_role_arns" {
  description = "IRSA role ARN per agent, for the service account annotations."
  value       = { for name, role in aws_iam_role.agent : name => role.arn }
}

output "agents_without_write_access" {
  description = "Agents holding no write policy at all. sati.orchestrator and sati.security must always appear here."
  value       = sort([for name, spec in local.agents : name if length(spec.write) == 0])
}
