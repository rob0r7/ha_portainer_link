# Contributing to HA Portainer Link

Thank you for your interest in contributing! 🎉  
This project is a custom [Home Assistant](https://www.home-assistant.io/) integration for controlling and monitoring Docker containers and stacks via Portainer.

## 🧪 Testing Help Wanted

If you’d like to help test new versions, we have a step-by-step volunteer checklist in the README:  
[How You Can Help Test](./README.md#-how-you-can-help-test)

It covers:
- Installation and initial setup sanity checks
- Validating container/stack sensors (status, uptime, CPU/memory, version/digest)
- Using container and stack controls (start/stop/restart/update)
- Testing built-in services (`refresh`, `reload`)
- Exercising common failure scenarios (endpoint, SSL, logger config)
- Reporting results with debug logs

Please **use a non-critical Portainer environment** or throwaway containers/stacks for testing, as these tests will start/stop/redeploy containers.

---

## 🛠 Development Contributions

If you want to work on code changes:
1. **Fork** this repository.
2. Create a **feature branch** for your changes.
3. Make changes in `custom_components/ha_portainer_link/`.
4. Test locally in your Home Assistant setup (you can use the testing checklist above to confirm functionality).
5. Submit a **Pull Request** with:
   - Clear description of changes
   - Any new dependencies or configuration changes
   - Steps to reproduce/test the change

---

## 📜 Code Style

- Follow the Home Assistant [Custom Integration Development Guidelines](https://developers.home-assistant.io/docs/creating_component_index/).
- Use Python type hints where possible.
- Keep logging informative but not overly noisy.
- Maintain backward compatibility with HA 2023.8.0+ unless otherwise discussed.

---

## 📝 License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
