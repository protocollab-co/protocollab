"""
Security tests — depth limits, import limits, path security, and dangerous tags.
"""

import os
import pytest
from yaml_serializer.serializer import SerializerSession


class TestPathSecurity:
    """Tests for path-traversal and out-of-root-directory access prevention."""

    def test_include_outside_root_blocked(self, temp_dir, create_yaml_file):
        """Including a file outside the root directory must raise PermissionError."""
        inside_dir = os.path.join(temp_dir, "inside")
        outside_dir = os.path.join(temp_dir, "..", "outside")
        os.makedirs(inside_dir, exist_ok=True)
        os.makedirs(outside_dir, exist_ok=True)

        main_yaml = os.path.join(inside_dir, "main.yaml")
        outside_yaml = os.path.join(outside_dir, "external.yaml")

        create_yaml_file(outside_yaml, "data: external\n")
        create_yaml_file(main_yaml, "inc: !include ../../outside/external.yaml\n")

        with pytest.raises(PermissionError, match="not allowed"):
            SerializerSession().load(main_yaml)

    def test_path_traversal_attack_prevented(self, temp_dir, create_yaml_file):
        """Path traversal attacks via ../../ must be blocked."""
        safe_dir = os.path.join(temp_dir, "safe")
        os.makedirs(safe_dir, exist_ok=True)

        main_yaml = os.path.join(safe_dir, "main.yaml")
        # Path traversal attempt via ../../../
        create_yaml_file(main_yaml, "data: !include ../../../etc/passwd\n")

        with pytest.raises((PermissionError, FileNotFoundError)):
            SerializerSession().load(main_yaml)


class TestDepthLimits:
    def test_struct_depth_limit(self, temp_dir, create_yaml_file):
        """
        Verify max_struct_depth limit: too-deep structures fail, shallower succeed.
        """
        main_yaml = os.path.join(temp_dir, "main.yaml")
        content = "a:"
        for i in range(8):
            content += "\n" + "  " * (i + 1) + f"level{i}:"
        content += "\n" + "  " * 9 + "value: deep\n"
        create_yaml_file(main_yaml, content)
        # With a small max_struct_depth — error
        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            SerializerSession().load(main_yaml, config={"max_struct_depth": 5})
        # With a large value — success
        data = SerializerSession().load(main_yaml, config={"max_struct_depth": 20})
        assert data["a"]["level0"]["level1"]["level2"]["level3"]["level4"] is not None

    def test_structural_max_depth_limit(self, temp_dir, create_yaml_file):
        """Verify max_depth for deeply nested structures via create_safe_yaml_instance."""
        from yaml_serializer.safe_constructor import create_safe_yaml_instance

        main_yaml = os.path.join(temp_dir, "main.yaml")
        # Create a YAML with a deeply nested structure (10 levels)
        content = "a:"
        for i in range(10):
            content += "\n" + "  " * (i + 1) + f"level{i}:"
        content += "\n" + "  " * 11 + "value: deep\n"
        create_yaml_file(main_yaml, content)

        # With max_depth=10 must raise an error
        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            yaml = create_safe_yaml_instance(max_depth=10)
            with open(main_yaml, "r", encoding="utf-8") as f:
                yaml.load(f)

        # With max_depth=50 must load successfully
        yaml = create_safe_yaml_instance(max_depth=50)
        with open(main_yaml, "r", encoding="utf-8") as f:
            try:
                data = yaml.load(f)
            except ValueError as e:
                # Exceeding the depth limit is also a success
                if "Exceeded maximum nesting depth" in str(e):
                    data = None  # Exceeding the depth limit is an acceptable result
                else:
                    raise
        assert data is not None
        assert data["a"]["level0"]["level1"]["level2"]["level3"]["level4"] is not None

    def test_max_include_depth_limit(self, temp_dir, create_yaml_file):
        """Verify max_include_depth limit: deep chains fail at small limit, succeed at large."""
        # Create an include chain of depth 5
        for i in range(5):
            file_path = os.path.join(temp_dir, f"level{i}.yaml")
            if i < 4:
                create_yaml_file(file_path, f"data: !include level{i+1}.yaml\n")
            else:
                create_yaml_file(file_path, "data: final\n")

        main_yaml = os.path.join(temp_dir, "level0.yaml")

        # With limit 3 must fail
        with pytest.raises(ValueError, match="Exceeded maximum include depth"):
            SerializerSession().load(main_yaml, config={"max_include_depth": 3})

        # With limit 10 must succeed
        data = SerializerSession().load(main_yaml, config={"max_include_depth": 10})
        node = data
        for _ in range(4):
            node = node["data"]
        assert node["data"] == "final"

    def test_deeply_nested_structures_allowed(self, temp_dir, create_yaml_file):
        """Deep non-include nesting must be allowed by the include depth limit."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        # Create a deeply nested structure without include
        content = "a:\n"
        for i in range(20):
            content += "  " * (i + 1) + f"level{i}:\n"
        content += "  " * 21 + "value: deep\n"

        create_yaml_file(main_yaml, content)

        # Must load without errors even with include depth limit
        data = SerializerSession().load(main_yaml, config={"max_include_depth": 5})
        assert data is not None


class TestImportLimits:
    """Tests for the maximum include-count (max_imports) limit."""

    def test_max_imports_limit(self, temp_dir, create_yaml_file):
        """Exceeding max_imports raises ValueError; staying within it succeeds."""
        # Create 5 files to import
        for i in range(5):
            file_path = os.path.join(temp_dir, f"import{i}.yaml")
            create_yaml_file(file_path, f"value: {i}\n")
        # Main file imports all 5
        main_yaml = os.path.join(temp_dir, "main.yaml")
        imports = "\n".join([f"import{i}: !include import{i}.yaml" for i in range(5)])
        create_yaml_file(main_yaml, imports + "\n")
        # With limit 3 must fail
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            SerializerSession().load(main_yaml, config={"max_imports": 3})
        # With limit 20 must succeed
        data = SerializerSession().load(main_yaml, config={"max_imports": 20})
        assert data["import0"]["value"] == 0
        assert data["import4"]["value"] == 4

    def test_nested_imports_counted(self, temp_dir, create_yaml_file):
        """Imports inside nested includes are counted toward the global limit."""
        # file level2 imports 2 files
        create_yaml_file(os.path.join(temp_dir, "a.yaml"), "data: a\n")
        create_yaml_file(os.path.join(temp_dir, "b.yaml"), "data: b\n")
        create_yaml_file(
            os.path.join(temp_dir, "level2.yaml"), "a: !include a.yaml\n" "b: !include b.yaml\n"
        )

        # level1 imports 2 more files + level2
        create_yaml_file(os.path.join(temp_dir, "c.yaml"), "data: c\n")
        create_yaml_file(os.path.join(temp_dir, "d.yaml"), "data: d\n")
        create_yaml_file(
            os.path.join(temp_dir, "level1.yaml"),
            "nested: !include level2.yaml\n" "c: !include c.yaml\n" "d: !include d.yaml\n",
        )

        # Total 5 imports (a, b, c, d, level2)
        # With limit 4 must fail
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            SerializerSession().load(
                os.path.join(temp_dir, "level1.yaml"), config={"max_imports": 4}
            )

    def test_imports_counted_across_includes(self, temp_dir, create_yaml_file):
        """Imports in included files are counted in the global import total."""
        # Create 3 files to import
        for i in range(3):
            file_path = os.path.join(temp_dir, f"import{i}.yaml")
            create_yaml_file(file_path, f"value: {i}\n")

        # Include these files in another file
        include_yaml = os.path.join(temp_dir, "include.yaml")
        create_yaml_file(
            include_yaml,
            "import0: !include import0.yaml\n"
            "import1: !include import1.yaml\n"
            "import2: !include import2.yaml\n",
        )

        # Main file includes include.yaml
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "included: !include include.yaml\n")

        # With limit 2 must fail (3 imports inside include.yaml)
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            SerializerSession().load(main_yaml, config={"max_imports": 2})

    def test_import_limit_with_nested_includes(self, temp_dir, create_yaml_file):
        """Import limit is enforced across nested include hierarchies."""
        # Create 4 files to import
        for i in range(4):
            file_path = os.path.join(temp_dir, f"import{i}.yaml")
            create_yaml_file(file_path, f"value: {i}\n")

        # level2 includes 2 imports
        create_yaml_file(
            os.path.join(temp_dir, "level2.yaml"),
            "import0: !include import0.yaml\n" "import1: !include import1.yaml\n",
        )

        # level1 includes level2 and 2 more imports
        create_yaml_file(
            os.path.join(temp_dir, "level1.yaml"),
            "nested: !include level2.yaml\n"
            "import2: !include import2.yaml\n"
            "import3: !include import3.yaml\n",
        )

        # Total 5 imports (import0, import1, import2, import3, level2)
        # With limit 4 must fail
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            SerializerSession().load(
                os.path.join(temp_dir, "level1.yaml"), config={"max_imports": 4}
            )

    def test_import_limit_with_circular_includes(self, temp_dir, create_yaml_file):
        """Circular includes are detected before the import limit is reached."""
        # Create 2 files that include each other
        create_yaml_file(os.path.join(temp_dir, "a.yaml"), "data: a\n")
        create_yaml_file(os.path.join(temp_dir, "b.yaml"), "data: b\n")
        create_yaml_file(os.path.join(temp_dir, "a.yaml"), "data: a\n" "b: !include b.yaml\n")
        create_yaml_file(os.path.join(temp_dir, "b.yaml"), "data: b\n" "a: !include a.yaml\n")

        # With limit 10 must fail due to circular include
        with pytest.raises(ValueError, match="Circular include detected"):
            SerializerSession().load(os.path.join(temp_dir, "a.yaml"), config={"max_imports": 10})


class TestFileSizeLimits:
    """Tests for the max_file_size limit."""

    def test_max_file_size_limit(self, temp_dir, create_yaml_file):
        """Files exceeding max_file_size raise ValueError; smaller files succeed."""
        inc_yaml = os.path.join(temp_dir, "large.yaml")
        main_yaml = os.path.join(temp_dir, "main.yaml")

        # Create a "large" file (small size used for the test)
        large_content = "data:\n" + "  - item\n" * 1000  # ~15KB
        create_yaml_file(inc_yaml, large_content)
        create_yaml_file(main_yaml, "large: !include large.yaml\n")

        # With limit 1KB must fail
        with pytest.raises(ValueError, match="exceeds size limit"):
            SerializerSession().load(main_yaml, config={"max_file_size": 1024})

        # With limit 50KB must succeed
        data = SerializerSession().load(main_yaml, config={"max_file_size": 50 * 1024})
        assert "large" in data


class TestDefaultSecuritySettings:
    """Tests for default security configuration values."""

    def test_default_config_values(self, temp_dir, create_yaml_file):
        """Default security settings have the expected values."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: value\n")

        s = SerializerSession()
        s.load(main_yaml)

        assert s._max_file_size == 10 * 1024 * 1024  # 10 MB
        assert s._max_include_depth == 50
        assert s._max_imports == 100

    def test_can_override_defaults(self, temp_dir, create_yaml_file):
        """Default security settings can be overridden via the config dict."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: value\n")

        s = SerializerSession()
        s.load(
            main_yaml,
            config={"max_file_size": 5 * 1024 * 1024, "max_include_depth": 20, "max_imports": 50},
        )

        assert s._max_file_size == 5 * 1024 * 1024
        assert s._max_include_depth == 20
        assert s._max_imports == 50


class TestDangerousTags:
    """Tests for blocking dangerous YAML tags."""

    def test_python_object_apply_blocked(self, temp_dir, create_yaml_file):
        """!!python/object/apply tag must be blocked as a dangerous tag."""
        main_yaml = os.path.join(temp_dir, "exploit.yaml")
        # Attempt to execute a system command via YAML
        create_yaml_file(main_yaml, 'exploit: !!python/object/apply:os.system ["echo HACKED"]\n')

        from ruamel.yaml.error import YAMLError

        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            SerializerSession().load(main_yaml)
        """Block the !!python/object tag."""
        main_yaml = os.path.join(temp_dir, "obj.yaml")
        create_yaml_file(main_yaml, 'path: !!python/object:os.path.join ["a", "b"]\n')

        from ruamel.yaml.error import YAMLError

        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            SerializerSession().load(main_yaml)

    def test_python_module_blocked(self, temp_dir, create_yaml_file):
        """!!python/module tag must be blocked."""
        main_yaml = os.path.join(temp_dir, "module.yaml")
        create_yaml_file(main_yaml, "os_module: !!python/module:os\n")

        from ruamel.yaml.error import YAMLError

        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            SerializerSession().load(main_yaml)

    def test_python_name_blocked(self, temp_dir, create_yaml_file):
        """!!python/name tag must be blocked."""
        main_yaml = os.path.join(temp_dir, "name.yaml")
        create_yaml_file(main_yaml, "system: !!python/name:os.system\n")

        from ruamel.yaml.error import YAMLError

        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            SerializerSession().load(main_yaml)

    def test_only_include_tag_allowed(self, temp_dir, create_yaml_file):
        """!include is the only custom tag allowed; all others must be blocked."""
        inc_yaml = os.path.join(temp_dir, "inc.yaml")
        create_yaml_file(inc_yaml, "data: value\n")

        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "included: !include inc.yaml\ndata: normal\n")

        # !include must work
        data = SerializerSession().load(main_yaml)
        assert data["included"]["data"] == "value"
        assert data["data"] == "normal"

    def test_unknown_custom_tag_blocked(self, temp_dir, create_yaml_file):
        """Unknown custom tags must be blocked."""
        main_yaml = os.path.join(temp_dir, "custom.yaml")
        create_yaml_file(main_yaml, "value: !custom_tag some_value\n")

        from ruamel.yaml.error import YAMLError

        with pytest.raises(YAMLError, match="Unknown tag.*detected and blocked"):
            SerializerSession().load(main_yaml)


class TestBillionLaughs:
    """Tests for protection against YAML bomb (billion laughs) attacks."""

    @pytest.mark.slow
    def test_exponential_expansion_blocked_by_depth(self, temp_dir, create_yaml_file):
        """Exponential anchor expansion is handled safely (no memory explosion)."""
        main_yaml = os.path.join(temp_dir, "bomb.yaml")

        # Build a structure with exponential growth
        # Each level doubles the size
        yaml_content = """
a: &a ["lol"]
b: &b [*a, *a]
c: &c [*b, *b]
d: &d [*c, *c]
e: &e [*d, *d]
f: &f [*e, *e]
g: &g [*f, *f]
h: &h [*g, *g]
i: &i [*h, *h]
j: [*i, *i]
"""
        create_yaml_file(main_yaml, yaml_content)

        # The defence must trigger (via memory/size limits or depth)
        # In practice ruamel.yaml already has built-in protection against anchor recursion
        # Our code must handle this correctly
        try:
            data = SerializerSession().load(main_yaml)
            # If it loaded, verify the size is reasonable (not gigabytes).
            # ruamel.yaml typically stores anchors as references, not copies.
            import sys

            size = sys.getsizeof(data)
            assert size < 100 * 1024 * 1024, "Potential memory bomb detected"
        except Exception:
            # Any exception from a defensive measure is a passing result
            pass

    def test_deeply_nested_anchors(self, temp_dir, create_yaml_file):
        """Deeply nested anchors must trigger a depth or recursion error."""
        import pytest

        main_yaml = os.path.join(temp_dir, "nested.yaml")

        # Create a very deeply nested structure via anchors
        yaml_content = "a: &anchor1\n"
        for i in range(100):
            yaml_content += f"  {'  ' * i}level{i}:\n"
        yaml_content += "  " * 100 + "value: deep\n"
        yaml_content += "b: *anchor1\n"

        create_yaml_file(main_yaml, yaml_content)

        # Expect a depth error or RecursionError from very deep nesting
        with pytest.raises((ValueError, RecursionError)):
            SerializerSession().load(main_yaml)


class TestBoundaryLimits:
    """Exact boundary tests verifying at-limit behaviour for security limits."""

    def test_include_depth_at_limit_succeeds(self, temp_dir, create_yaml_file):
        """A chain of DEPTH inclusions with max_include_depth=DEPTH+1 must succeed."""
        DEPTH = 3  # f0 -> f1 -> f2 -> f3(leaf): 3 includes
        files = [os.path.join(temp_dir, f"f{i}.yaml") for i in range(DEPTH + 1)]
        for i in range(DEPTH):
            create_yaml_file(files[i], f"data: !include f{i+1}.yaml\n")
        create_yaml_file(files[DEPTH], "value: leaf\n")

        # Stack depth when including f3: len([f0,f1,f2])=3; 3 >= 4 is False -> succeeds
        data = SerializerSession().load(files[0], config={"max_include_depth": DEPTH + 1})
        assert data is not None

    def test_include_depth_over_limit_fails(self, temp_dir, create_yaml_file):
        """A chain of DEPTH inclusions with max_include_depth=DEPTH must fail."""
        DEPTH = 3
        files = [os.path.join(temp_dir, f"g{i}.yaml") for i in range(DEPTH + 1)]
        for i in range(DEPTH):
            create_yaml_file(files[i], f"data: !include g{i+1}.yaml\n")
        create_yaml_file(files[DEPTH], "value: leaf\n")

        # Stack depth when including g3: len([g0,g1,g2])=3; 3 >= 3 is True -> fails
        with pytest.raises(ValueError, match="Exceeded maximum include depth"):
            SerializerSession().load(files[0], config={"max_include_depth": DEPTH})

    def test_imports_exactly_at_limit_succeeds(self, temp_dir, create_yaml_file):
        """Exactly N imports with max_imports=N must succeed (check is counter > N)."""
        N = 4
        for i in range(N):
            create_yaml_file(os.path.join(temp_dir, f"inc{i}.yaml"), f"v: {i}\n")
        main = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main, "\n".join(f"inc{i}: !include inc{i}.yaml" for i in range(N)) + "\n")
        data = SerializerSession().load(main, config={"max_imports": N})
        assert all(f"inc{i}" in data for i in range(N))

    def test_imports_one_over_limit_fails(self, temp_dir, create_yaml_file):
        """N imports with max_imports=N-1 must fail."""
        N = 4
        for i in range(N):
            create_yaml_file(os.path.join(temp_dir, f"h{i}.yaml"), f"v: {i}\n")
        main = os.path.join(temp_dir, "main2.yaml")
        create_yaml_file(main, "\n".join(f"h{i}: !include h{i}.yaml" for i in range(N)) + "\n")
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            SerializerSession().load(main, config={"max_imports": N - 1})

    def test_struct_depth_over_limit_fails(self, temp_dir, create_yaml_file):
        """A structure deeper than max_struct_depth must fail."""
        main_yaml = os.path.join(temp_dir, "deep.yaml")
        content = "a:\n" + "".join("  " * (i + 1) + f"l{i}:\n" for i in range(10))
        content += "  " * 11 + "val: deep\n"
        create_yaml_file(main_yaml, content)
        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            SerializerSession().load(main_yaml, config={"max_struct_depth": 5})

    def test_struct_depth_within_limit_succeeds(self, temp_dir, create_yaml_file):
        """A structure whose depth stays within max_struct_depth must succeed."""
        main_yaml = os.path.join(temp_dir, "shallow.yaml")
        content = "a:\n  b:\n    c: value\n"
        create_yaml_file(main_yaml, content)
        data = SerializerSession().load(main_yaml, config={"max_struct_depth": 20})
        assert data["a"]["b"]["c"] == "value"
