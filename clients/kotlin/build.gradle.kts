import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    kotlin("jvm") version "1.9.24"
    kotlin("plugin.serialization") version "1.9.24"
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1"
    `java-library`
    `maven-publish`
}

group = "org.aigen"
version = "0.1.0"
description = "OABP Kotlin SDK — coroutine client for the OABP / AIGEN agent-bounty protocol"

repositories {
    mavenCentral()
}

object Versions {
    const val KTOR = "2.3.12"
    const val SERIALIZATION = "1.6.3"
    const val COROUTINES = "1.8.1"
    const val JUNIT = "5.10.2"
}

dependencies {
    // Coroutines + kotlinx.serialization are part of the public API surface
    // (suspend functions return @Serializable data classes).
    api("org.jetbrains.kotlinx:kotlinx-serialization-json:${Versions.SERIALIZATION}")
    api("org.jetbrains.kotlinx:kotlinx-coroutines-core:${Versions.COROUTINES}")

    // Ktor HTTP client.
    api("io.ktor:ktor-client-core:${Versions.KTOR}")
    implementation("io.ktor:ktor-client-cio:${Versions.KTOR}")
    implementation("io.ktor:ktor-client-content-negotiation:${Versions.KTOR}")
    implementation("io.ktor:ktor-serialization-kotlinx-json:${Versions.KTOR}")

    testImplementation("io.ktor:ktor-client-mock:${Versions.KTOR}")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:${Versions.COROUTINES}")
    testImplementation(platform("org.junit:junit-bom:${Versions.JUNIT}"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(17)
    }
    withSourcesJar()
}

kotlin {
    jvmToolchain(17)
    explicitApi()
}

// A dedicated source set for the runnable example under examples/. It compiles against the
// main library so the example is build-verified (it is not part of the published jar).
sourceSets {
    create("examples") {
        // Source lives in the repo-root examples/ directory, not src/examples/kotlin.
        java.setSrcDirs(listOf("examples"))
        compileClasspath += sourceSets.main.get().compileClasspath + sourceSets.main.get().output
        runtimeClasspath += sourceSets.main.get().runtimeClasspath + sourceSets.main.get().output
    }
}

dependencies {
    // The example uses the CIO engine directly (the library only exposes ktor-client-core in api).
    "examplesImplementation"("io.ktor:ktor-client-cio:${Versions.KTOR}")
    "examplesImplementation"("org.jetbrains.kotlinx:kotlinx-coroutines-core:${Versions.COROUTINES}")
}

tasks.withType<KotlinCompile>().configureEach {
    compilerOptions {
        freeCompilerArgs.add("-Xjsr305=strict")
    }
}

// Don't force explicit-API visibility on the example's top-level main().
tasks.named<KotlinCompile>("compileExamplesKotlin") {
    compilerOptions {
        freeCompilerArgs.add("-Xexplicit-api=disable")
    }
}

// Build the example as part of `check` so it can never silently rot.
tasks.named("check") {
    dependsOn("compileExamplesKotlin")
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}

ktlint {
    version.set("1.2.1")
    ignoreFailures.set(false)
    filter {
        // Never lint generated/build output.
        exclude { it.file.path.contains("${layout.buildDirectory.get()}") }
    }
}

publishing {
    publications {
        create<MavenPublication>("mavenKotlin") {
            from(components["java"])
            artifactId = "oabp-kotlin-sdk"
            pom {
                name.set("OABP Kotlin SDK")
                description.set(project.description)
                licenses {
                    license {
                        name.set("MIT License")
                        url.set("https://opensource.org/licenses/MIT")
                    }
                }
            }
        }
    }
}
