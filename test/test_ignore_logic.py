import unittest
import os
from dir_assistant.assistant.index import _is_path_ignored


class TestIgnoreLogic(unittest.TestCase):
    def test_basic_ignore_patterns(self):
        """Test basic ignore patterns without globs"""
        test_cases = [
            # Basic directory ignore
            ("src/node_modules/package.json", "node_modules", True),
            ("project/src/dist/bundle.js", "dist", True),
            ("src/some_folder/file.txt", "node_modules", False),
            
            # Nested paths
            ("frontend/src/node_modules/deep/package.json", "node_modules", True),
            ("backend/src/tests/dist/output.js", "dist", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_glob_patterns(self):
        """Test different glob pattern combinations"""
        test_cases = [
            # Single star patterns
            ("src/test123/file.txt", "test*/file.txt", True),
            ("src/test/file123.txt", "test/*.txt", True),
            ("src/test/subdir/file.txt", "test/*.txt", False),
            
            # Double star patterns
            ("very/deep/node_modules/package.json", "**/node_modules/**", True),
            ("node_modules/package.json", "**/node_modules/**", True),
            ("src/lib/node_modules/deep/pkg/file.js", "**/node_modules/**", True),
            ("src/nodemodules/file.js", "**/node_modules/**", False),
            
            # Complex patterns
            ("src/test/java/com/example/Test.java", "**/test/**/*.java", True),
            ("src/main/java/com/example/Test.java", "**/test/**/*.java", False),
            ("test/unit/some/path/file.ts", "**/test/**/*.ts", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_build_and_dependency_patterns(self):
        """Test common build and dependency patterns"""
        test_cases = [
            # Node.js
            ("frontend/node_modules/react/index.js", "**/node_modules/**", True),
            ("package-lock.json", "**/package-lock.json", True),
            ("app/yarn.lock", "**/yarn.lock", True),
            
            # Python
            ("src/__pycache__/module.pyc", "**/__pycache__/**", True),
            ("tests/.pytest_cache/CACHEDIR.TAG", "**/.pytest_cache/**", True),
            (".venv/lib/python3.8/site-packages/pkg.py", "**/.venv/**", True),
            
            # Java/Maven
            ("build/classes/main/App.class", "**/build/**/*.class", True),
            ("target/myapp-1.0.jar", "**/target/**/*.jar", True),
            (".gradle/7.0/checksums", "**/.gradle/**", True),
            ("modules/shared/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst", "**/target/**", True),
            ("project/module/target/classes/com/example/Test.class", "**/target/**", True),
            ("target/maven-status/maven-compiler-plugin/testCompile/default-testCompile/inputFiles.lst", "**/target/**", True),
            ("target/maven-archiver/pom.properties", "**/target/**", True),
            ("target/surefire-reports/TEST-com.example.TestClass.xml", "**/target/**", True),
            ("target/site/jacoco/index.html", "**/target/**", True),
            ("target/generated-sources/annotations/", "**/target/**", True),
            ("some-module/target/dependency-reduced-pom.xml", "**/target/**", True),
            ("deep/path/to/module/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst", "**/target/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_ide_and_editor_patterns(self):
        """Test IDE and editor specific patterns"""
        test_cases = [
            # VS Code
            (".vscode/settings.json", "**/.vscode/**", True),
            ("project/.vscode/launch.json", "**/.vscode/**", True),
            
            # JetBrains
            (".idea/workspace.xml", "**/.idea/**", True),
            ("project/.idea/misc.xml", "**/.idea/**", True),
            
            # Eclipse
            (".settings/org.eclipse.jdt.core.prefs", "**/.settings/**", True),
            (".project", "**/.project", True),
            
            # Vim
            ("src/file.txt.swp", "**/*.swp", True),
            (".config.swp", "**/*.swp", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_mobile_development_patterns(self):
        """Test mobile development specific patterns"""
        test_cases = [
            # iOS
            ("MyApp.xcodeproj/project.pbxproj", "**/*.xcodeproj/**", True),
            ("Pods/Firebase/Core/Sources/File.h", "**/Pods/**", True),
            ("build/MyApp.app.dSYM", "**/*.dSYM", True),
            
            # Android
            ("app/build/outputs/apk/debug/app.apk", "**/*.apk", True),
            (".gradle/buildOutputCleanup/cache.properties", "**/.gradle/**", True),
            ("local.properties", "**/local.properties", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_system_and_hidden_files(self):
        """Test system and hidden files patterns"""
        test_cases = [
            # macOS
            (".DS_Store", "**/.DS_Store", True),
            ("folder/.DS_Store", "**/.DS_Store", True),
            
            # Windows
            ("Thumbs.db", "**/Thumbs.db", True),
            ("folder/Thumbs.db", "**/Thumbs.db", True),
            
            # Git
            (".git/config", "**/.git/**", True),
            ("submodule/.git/HEAD", "**/.git/**", True),
            (".gitignore", "**/.gitignore", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_path_edge_cases(self):
        """Test edge cases and special path patterns"""
        test_cases = [
            # Empty paths
            ("", "**/node_modules/**", False),
            ("", "", True),
            
            # Root level matches
            ("node_modules", "**/node_modules/**", True),
            (".git", "**/.git/**", True),
            
            # Complex nesting
            ("a/b/c/d/e/node_modules/f/g/h", "**/node_modules/**", True),
            ("very/deep/path/with/.git/at/the/middle", "**/.git/**", True),
            
            # Multiple patterns in path
            ("test/node_modules/test/node_modules", "**/node_modules/**", True),
            
            # Special characters
            ("path/with spaces/node_modules", "**/node_modules/**", True),
            ("path/with-hyphens/dist", "**/dist/**", True),
            ("path/with.dots/build", "**/build/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_case_sensitivity(self):
        """Test case insensitive matching"""
        test_cases = [
            # Mixed case in path
            ("src/Node_Modules/package.json", "**/node_modules/**", True),
            ("SRC/DIST/bundle.js", "**/dist/**", True),
            
            # Mixed case in pattern
            ("src/node_modules/file.js", "**/NODE_MODULES/**", True),
            ("src/dist/file.js", "**/DiSt/**", True),
            
            # Mixed case in both
            ("src/Node_Modules/Dist/Bundle.js", "**/node_modules/**", True),
            ("SRC/DIST/PACKAGE.JSON", "**/dist/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_backward_compatibility(self):
        """Test that old pattern styles still work"""
        test_cases = [
            # Original test cases
            ("my_projects/tst/src/main/resources/swagger/swagger-ui-core.js.map", "resources/swagger/", True),
            ("my_projects/tst/src/resources/swagger/swagger-ui-core.js.map", "resources/swagger/", True),
            ("my_projects/tst/src/main/resources/some-other-folder/file.txt", "resources/swagger/", False),
            (r"C:\workspace\projects\pool\src\main\resources\swagger\swagger-ui-es-bundle-core.js.map", "resources/swagger/", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_relative_path_scenarios(self):
        """Test ignore patterns with relative paths and different working directories"""
        test_cases = [
            # When working dir is /workspace/projects/empty and target dir is ../pool
            ("modules/shared/target/classes/com/example/Test.class", "**/target/**", True),
            ("modules/shared/src/main/java/com/example/Test.java", "**/target/**", False),
            
            # Deeply nested target directories
            ("some/very/deep/path/target/classes/file.class", "**/target/**", True),
            ("another/deep/path/not-target/classes/file.class", "**/target/**", False),
            
            # Complex relative paths
            ("../pool/modules/shared/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst", "**/target/**", True),
            ("../pool/modules/core/src/main/resources/config.xml", "**/target/**", False),
            
            # Parent directory references
            ("../../other-project/target/classes/file.class", "**/target/**", True),
            ("../sibling-project/build/libs/file.jar", "**/target/**", False),
            
            # Mixed path separators
            (r"..\pool\modules\shared\target\classes\Test.class", "**/target/**", True),
            (r"..\pool\modules\shared\src\main\java\Test.java", "**/target/**", False),
            
            # Absolute paths when working from relative directory
            ("/workspace/projects/pool/modules/shared/target/classes/Test.class", "**/target/**", True),
            ("/workspace/projects/pool/modules/shared/src/main/java/Test.java", "**/target/**", False),
            
            # Current directory references
            ("./target/classes/Test.class", "**/target/**", True),
            ("./src/main/java/Test.java", "**/target/**", False),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)

    def test_working_directory_edge_cases(self):
        """Test ignore patterns with tricky working directory scenarios"""
        test_cases = [
            # Empty relative paths
            ("", "**/target/**", False),
            (".", "**/target/**", False),
            ("..", "**/target/**", False),
            
            # Just the pattern directory
            ("target", "**/target/**", True),
            ("./target", "**/target/**", True),
            ("../target", "**/target/**", True),
            
            # Relative paths with multiple parent references
            ("../../target/classes/Test.class", "**/target/**", True),
            ("../../../very/deep/target/classes/Test.class", "**/target/**", True),
            
            # Mixed absolute and relative paths
            ("/absolute/path/to/target/classes/Test.class", "**/target/**", True),
            ("../relative/path/to/target/classes/Test.class", "**/target/**", True),
            ("./current/path/to/target/classes/Test.class", "**/target/**", True),
            
            # Path traversal attempts
            ("../../../etc/passwd", "**/target/**", False),
            ("target/../../../etc/passwd", "**/target/**", False),
            
            # Windows-style paths with drive letters
            (r"C:\workspace\projects\pool\target\classes\Test.class", "**/target/**", True),
            (r"D:\another\path\target\classes\Test.class", "**/target/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(_is_path_ignored(path, pattern), expected)


if __name__ == '__main__':
    unittest.main() 