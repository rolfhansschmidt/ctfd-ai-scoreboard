// Progressive enhancement recommended by CTFd's custom field dropdown guide.
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById(`fields[${aiUsageConfig.field}]`);
  if (!input || input.tagName !== "INPUT") return;
  const select = document.createElement("select");
  select.id = input.id;
  select.name = input.name;
  select.className = "form-select";
  select.required = true;
  select.dataset.initial = input.value;
  select.add(new Option("Choose your team's AI usage", ""));
  Object.keys(aiUsageConfig.states).forEach(value => select.add(new Option(value, value)));
  select.value = input.value;
  input.replaceWith(select);
  const bracket = document.getElementById("bracket_id");
  if (bracket) {
    bracket.hidden = true;
    bracket.required = false;
    document.querySelectorAll('label[for="bracket_id"]').forEach(label => label.hidden = true);
    const sync = () => bracket.value = aiUsageConfig.states[select.value] || "";
    select.addEventListener("change", sync);
    sync();
  }
});
