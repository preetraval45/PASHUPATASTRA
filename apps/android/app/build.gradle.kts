plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// The address the app opens. CI can point a build at another deployment with -PsiteUrl=...
val siteUrl: String = (project.findProperty("siteUrl") as String?) ?: "https://pashupatastra.vercel.app"

android {
    namespace = "app.pashupatastra"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.pashupatastra"
        minSdk = 24
        targetSdk = 35
        // CI sets the build number from the run, so each APK installs over the last.
        versionCode = ((project.findProperty("versionCode") as String?) ?: "1").toInt()
        versionName = (project.findProperty("versionName") as String?) ?: "0.1"
        buildConfigField("String", "SITE_URL", "\"$siteUrl\"")
    }

    signingConfigs {
        // A PUBLIC test key, committed on purpose so every CI build can install over the previous one.
        // It is for sideloaded test builds only. A store release gets its own private key, held as a
        // GitHub secret, never this one.
        create("test") {
            storeFile = rootProject.file("test-signing.jks")
            storePassword = "android"
            keyAlias = "pashupatastra-test"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("test")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("androidx.core:core-splashscreen:1.0.1")
}
