import { loadPyodide, type PyodideInterface } from 'pyodide';

declare global {
	interface Window {
		stdout: string | null;
		stderr: string | null;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		result: any;
		pyodide: PyodideInterface;
		packages: string[];
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		[key: string]: any;
	}
}

async function loadPyodideAndPackages(packages: string[] = []) {
	self.stdout = null;
	self.stderr = null;
	self.result = null;

	self.pyodide = await loadPyodide({
		indexURL: '/pyodide/',
		stdout: (text) => {
			if (self.stdout) {
				self.stdout += `${text}\n`;
			} else {
				self.stdout = `${text}\n`;
			}
		},
		stderr: (text) => {
			console.log('An error occurred:', text);
			if (self.stderr) {
				self.stderr += `${text}\n`;
			} else {
				self.stderr = `${text}\n`;
			}
		},
		packages: ['micropip']
	});

	const micropip = self.pyodide.pyimport('micropip');

	// await micropip.set_index_urls('https://pypi.org/pypi/{package_name}/json');
	if (packages.length > 0) {
		await micropip.install(packages);
	}
}

self.onmessage = async (event) => {
	const { id, code, ...context } = event.data;

	// The worker copies the context in its own "memory" (an object mapping name to values)
	for (const key of Object.keys(context)) {
		self[key] = context[key];
	}

	try {
		// make sure loading is done
		await loadPyodideAndPackages(self.packages);
		self.result = await self.pyodide.runPythonAsync(code);
	} catch (error) {
		self.stderr = error instanceof Error ? error.toString() : String(error);
	}
	self.postMessage({ id, result: self.result, stdout: self.stdout, stderr: self.stderr });
};

export default {};
