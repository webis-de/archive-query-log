const { Project, Node, SyntaxKind } = require("ts-morph");

const project = new Project({
  tsConfigFilePath: "tsconfig.json",
  skipAddingFilesFromTsConfig: true,
});

project.addSourceFilesAtPaths(["src/**/*.ts", "projects/**/*.ts"]);

const getAccessibility = member => {
  if (member.hasModifier(SyntaxKind.PrivateKeyword)) return "private";
  if (member.hasModifier(SyntaxKind.ProtectedKeyword)) return "protected";
  return "public";
};

const getOrderKey = member => {
  const accessibility = getAccessibility(member);
  if (Node.isConstructorDeclaration(member)) {
    return `${accessibility}-constructor`;
  }
  if (Node.isMethodDeclaration(member)) {
    return `${accessibility}-method`;
  }
  if (Node.isGetAccessorDeclaration(member) || Node.isSetAccessorDeclaration(member)) {
    return `${accessibility}-method`;
  }
  if (Node.isPropertyDeclaration(member)) {
    const isStatic = member.isStatic();
    const scope = isStatic ? "static" : "instance";
    return `${accessibility}-${scope}-field`;
  }
  return "unknown";
};

const ORDER = [
  "public-static-field",
  "protected-static-field",
  "private-static-field",
  "public-instance-field",
  "protected-instance-field",
  "private-instance-field",
  "public-constructor",
  "protected-constructor",
  "private-constructor",
  "public-method",
  "protected-method",
  "private-method",
  "unknown",
];

const orderIndex = key => {
  const index = ORDER.indexOf(key);
  return index === -1 ? ORDER.length - 1 : index;
};

const sortMembers = members =>
  members
    .map((member, index) => ({
      member,
      index,
      key: getOrderKey(member),
    }))
    .sort((a, b) => {
      const keyDiff = orderIndex(a.key) - orderIndex(b.key);
      if (keyDiff !== 0) return keyDiff;
      return a.index - b.index;
    })
    .map(item => item.member);

const getMemberCategory = member => {
  if (Node.isConstructorDeclaration(member)) return "function";
  if (Node.isMethodDeclaration(member)) return "function";
  if (Node.isGetAccessorDeclaration(member) || Node.isSetAccessorDeclaration(member)) {
    return "function";
  }
  if (Node.isPropertyDeclaration(member)) return "field";
  return "unknown";
};

for (const sourceFile of project.getSourceFiles()) {
  const classes = sourceFile
    .getClasses()
    .sort((a, b) => b.getPos() - a.getPos());
  if (classes.length === 0) continue;

  const fileText = sourceFile.getFullText();

  for (const classDecl of classes) {
    const members = classDecl.getMembers();
    if (members.length <= 1) continue;

    const sortedMembers = sortMembers(members);
    const memberEntries = sortedMembers.map(member => ({
      category: getMemberCategory(member),
      orderKey: getOrderKey(member),
      text: fileText
        .slice(member.getPos(), member.getEnd())
        .replace(/^[\r\n]+/, "")
        .replace(/[\r\n]+$/, ""),
    }));

    const lines = [""];
    let previousCategory = null;
    let previousOrderKey = null;
    for (const entry of memberEntries) {
      if (previousOrderKey && entry.orderKey !== previousOrderKey && lines[lines.length - 1] !== "") {
        lines.push("");
      }
      if (
        previousCategory &&
        (entry.category === "function" || previousCategory === "function") &&
        lines[lines.length - 1] !== ""
      ) {
        lines.push("");
      }
      lines.push(entry.text);
      previousCategory = entry.category;
      previousOrderKey = entry.orderKey;
    }

    const replacement = lines.join("\n");
    const start = members[0].getPos();
    const end = members[members.length - 1].getEnd();
    sourceFile.replaceText([start, end], replacement);
  }
}

project.saveSync();
